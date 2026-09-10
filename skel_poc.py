from __future__ import annotations
import io, json, zipfile, re, sys, subprocess, importlib, tempfile, os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

# Landmarks mínimos que ya están presentes en la secuencia V104/V107 y son útiles
# para el ajuste articular inicial de SKEL.
JOINTS = [
    "LHip","RHip","LKnee","RKnee","LAnkle","RAnkle",
    "LShoulder","RShoulder","LElbow","RElbow","LWrist","RWrist",
    "Neck","Head","Hip"
]

# Alias tolerantes para no depender de una única convención de nombres.
_ALIASES = {
    "lhip": "LHip", "lefthip": "LHip", "left_hip": "LHip", "hipleft": "LHip",
    "rhip": "RHip", "righthip": "RHip", "right_hip": "RHip", "hipright": "RHip",
    "lknee": "LKnee", "leftknee": "LKnee", "left_knee": "LKnee", "kneeleft": "LKnee",
    "rknee": "RKnee", "rightknee": "RKnee", "right_knee": "RKnee", "kneeright": "RKnee",
    "lankle": "LAnkle", "leftankle": "LAnkle", "left_ankle": "LAnkle", "ankleleft": "LAnkle",
    "rankle": "RAnkle", "rightankle": "RAnkle", "right_ankle": "RAnkle", "ankleright": "RAnkle",
    "lshoulder": "LShoulder", "leftshoulder": "LShoulder", "left_shoulder": "LShoulder",
    "rshoulder": "RShoulder", "rightshoulder": "RShoulder", "right_shoulder": "RShoulder",
    "lelbow": "LElbow", "leftelbow": "LElbow", "left_elbow": "LElbow",
    "relbow": "RElbow", "rightelbow": "RElbow", "right_elbow": "RElbow",
    "lwrist": "LWrist", "leftwrist": "LWrist", "left_wrist": "LWrist",
    "rwrist": "RWrist", "rightwrist": "RWrist", "right_wrist": "RWrist",
    "neck": "Neck", "head": "Head", "nose": "Nose", "hip": "Hip",
}

def _norm_name(name: str) -> str:
    s = str(name).strip()
    compact = re.sub(r"[^a-z0-9]", "", s.lower())
    # Primero coincidencia exacta canónica.
    for canon in JOINTS + ["Nose"]:
        if compact == re.sub(r"[^a-z0-9]", "", canon.lower()):
            return canon
    # Después alias con y sin separadores.
    raw = s.lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(raw, _ALIASES.get(compact, s))

def _xyz(v):
    try:
        if isinstance(v, dict):
            # Aceptar X/Y/Z y x/y/z.
            keys = {str(k).lower(): k for k in v.keys()}
            if all(k in keys for k in ("x","y","z")):
                a = [v[keys["x"]], v[keys["y"]], v[keys["z"]]]
            else:
                return None
        elif isinstance(v, (list, tuple, np.ndarray, pd.Series)) and len(v) >= 3:
            a = [v[0], v[1], v[2]]
        else:
            return None
        a = [float(x) for x in a]
        return a if np.isfinite(a).all() else None
    except Exception:
        return None

def _frame_points_from_frame(f):
    if not isinstance(f, dict):
        return {}
    # V104/V107 oficial usa `joints`; se mantienen los otros nombres como compatibilidad.
    src = f.get("joints")
    if not isinstance(src, dict) or not src:
        src = f.get("points")
    if not isinstance(src, dict) or not src:
        src = f.get("landmarks")
    if not isinstance(src, dict):
        return {}
    out = {}
    for k, v in src.items():
        p = _xyz(v)
        if p is not None:
            out[_norm_name(k)] = p

    # Centros derivados sólo para visualización/registro inicial. No sustituyen landmarks medidos.
    if "Hip" not in out and "LHip" in out and "RHip" in out:
        out["Hip"] = ((np.asarray(out["LHip"]) + np.asarray(out["RHip"])) / 2.0).tolist()
    if "Neck" not in out and "LShoulder" in out and "RShoulder" in out:
        out["Neck"] = ((np.asarray(out["LShoulder"]) + np.asarray(out["RShoulder"])) / 2.0).tolist()
    if "Head" not in out and "Nose" in out:
        out["Head"] = list(out["Nose"])
    return out

def _select_best_frame(motion):
    frames = list((motion or {}).get("frames") or [])
    best_i, best_pts, best_score = 0, {}, -1
    for i, f in enumerate(frames):
        pts = _frame_points_from_frame(f)
        score = sum(1 for j in JOINTS if j in pts)
        if score > best_score:
            best_i, best_pts, best_score = i, pts, score
        # 14+ ya es un frame excelente para este PoC; evitamos recorrer de más.
        if score >= 14:
            break
    return best_i, best_pts, max(0, best_score)

def _target_csv(points, frame_index=0):
    rows = []
    for j in JOINTS:
        if j in points:
            x, y, z = points[j]
            rows.append({"frame": int(frame_index)+1, "joint": j, "x": x, "y": y, "z": z,
                         "source": "derived" if j in ("Hip",) else "V104/V107"})
    return pd.DataFrame(rows)

def _inspect_private_bundle(data: bytes):
    info={"has_male":False,"has_female":False,"files":[],"valid_zip":False}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=z.namelist(); info["valid_zip"]=True
            info["files"]=names[:80]
            low=[n.lower() for n in names]
            info["has_male"]=any(n.endswith("skel_male.pkl") for n in low)
            info["has_female"]=any(n.endswith("skel_female.pkl") for n in low)
    except Exception as e:
        info["error"]=str(e)
    return info

def _plot_frame(df):
    if df.empty:
        return
    try:
        import plotly.graph_objects as go
        links = [
            ("LShoulder","RShoulder"),("LShoulder","LElbow"),("LElbow","LWrist"),
            ("RShoulder","RElbow"),("RElbow","RWrist"),("LShoulder","LHip"),
            ("RShoulder","RHip"),("LHip","RHip"),("LHip","LKnee"),("LKnee","LAnkle"),
            ("RHip","RKnee"),("RKnee","RAnkle"),("Neck","LShoulder"),("Neck","RShoulder"),("Neck","Head")
        ]
        P={r.joint:(r.x,r.y,r.z) for r in df.itertuples()}
        fig=go.Figure()
        for a,b in links:
            if a in P and b in P:
                xa,ya,za=P[a]; xb,yb,zb=P[b]
                fig.add_trace(go.Scatter3d(x=[xa,xb],y=[ya,yb],z=[za,zb],mode="lines",showlegend=False,hoverinfo="skip"))
        fig.add_trace(go.Scatter3d(x=df.x,y=df.y,z=df.z,mode="markers+text",text=df.joint,
                                   textposition="top center",name="Landmarks objetivo"))
        fig.update_layout(height=520,margin=dict(l=0,r=0,t=35,b=0),title="Frame objetivo V110.1.3 · XYZ para ajuste SKEL",
                          scene=dict(aspectmode="data"))
        st.plotly_chart(fig,use_container_width=True)
    except Exception as exc:
        st.caption(f"Visualización 3D no disponible: {exc}")



# V110.1.8 · correspondencia anatómica entre landmarks V104/V107 y joints SKEL.
# Se resuelve por nombre real del modelo (`model.joints_name`), evitando índices rígidos.
_SKEL_TARGET_CANDIDATES = {
    "Hip": ["pelvis"],
    "RHip": ["right_hip", "femur_r", "hip_r", "rhip"],
    "RKnee": ["right_knee", "tibia_r", "knee_r", "rknee"],
    "RAnkle": ["right_ankle", "talus_r", "ankle_r", "rankle"],
    "LHip": ["left_hip", "femur_l", "hip_l", "lhip"],
    "LKnee": ["left_knee", "tibia_l", "knee_l", "lknee"],
    "LAnkle": ["left_ankle", "talus_l", "ankle_l", "lankle"],
    "RShoulder": ["right_shoulder", "humerus_r", "shoulder_r", "rshoulder"],
    "RElbow": ["right_elbow", "ulna_r", "elbow_r", "relbow"],
    "RWrist": ["right_wrist", "hand_r", "wrist_r", "rwrist"],
    "LShoulder": ["left_shoulder", "humerus_l", "shoulder_l", "lshoulder"],
    "LElbow": ["left_elbow", "ulna_l", "elbow_l", "lelbow"],
    "LWrist": ["left_wrist", "hand_l", "wrist_l", "lwrist"],
    "Neck": ["neck", "cervical", "c7"],
    "Head": ["head", "skull"],
}

def _simple_name(v):
    if isinstance(v, bytes):
        try: v=v.decode("utf-8")
        except Exception: v=str(v)
    return re.sub(r"[^a-z0-9]", "", str(v).lower())

def _resolve_skel_correspondence(model, target_df):
    raw_names=getattr(model,"joints_name",[])
    names=list(raw_names) if raw_names is not None else []
    norm={_simple_name(n):i for i,n in enumerate(names)}
    rows=[]
    for target_name,cands in _SKEL_TARGET_CANDIDATES.items():
        if target_name not in set(target_df["joint"].astype(str)):
            continue
        found=None
        for cand in cands:
            key=_simple_name(cand)
            if key in norm:
                found=norm[key]; break
        if found is not None:
            rows.append((target_name,int(found),str(names[found])))
    return rows, names

def _rodrigues_torch(torch, r):
    # Rotación 3D diferenciable desde vector axis-angle.
    theta=torch.sqrt(torch.sum(r*r)+1e-12)
    k=r/theta
    K=torch.stack([
        torch.stack([torch.zeros_like(k[0]),-k[2],k[1]]),
        torch.stack([k[2],torch.zeros_like(k[0]),-k[0]]),
        torch.stack([-k[1],k[0],torch.zeros_like(k[0])])
    ])
    I=torch.eye(3,dtype=r.dtype,device=r.device)
    return I + torch.sin(theta)*K + (1.0-torch.cos(theta))*(K@K)

def _similarity_to_target(torch, src, tgt, rotvec):
    # src/tgt: Nx3. Rotación libre + escala isotrópica + traslación analítica.
    R=_rodrigues_torch(torch,rotvec)
    src_mean=src.mean(dim=0,keepdim=True)
    tgt_mean=tgt.mean(dim=0,keepdim=True)
    src_c=src-src_mean
    tgt_c=tgt-tgt_mean
    src_r=src_c @ R.T
    src_rms=torch.sqrt(torch.mean(torch.sum(src_r*src_r,dim=1))+1e-12)
    tgt_rms=torch.sqrt(torch.mean(torch.sum(tgt_c*tgt_c,dim=1))+1e-12)
    scale=tgt_rms/src_rms
    pred=src_r*scale+tgt_mean
    trans=tgt_mean.squeeze(0)-scale*(src_mean.squeeze(0) @ R.T)
    return pred,R,scale,trans

def _plot_skel_fit(target_df, fit_rows, before_xyz, after_xyz, all_after=None, all_names=None):
    try:
        import plotly.graph_objects as go
        target_map={r.joint:np.array([r.x,r.y,r.z],float) for r in target_df.itertuples()}
        names=[r[0] for r in fit_rows]
        T=np.stack([target_map[n] for n in names])
        fig=go.Figure()
        fig.add_trace(go.Scatter3d(x=T[:,0],y=T[:,1],z=T[:,2],mode="markers+text",text=names,textposition="top center",name="XYZ objetivo"))
        fig.add_trace(go.Scatter3d(x=before_xyz[:,0],y=before_xyz[:,1],z=before_xyz[:,2],mode="markers",name="SKEL antes"))
        fig.add_trace(go.Scatter3d(x=after_xyz[:,0],y=after_xyz[:,1],z=after_xyz[:,2],mode="markers+text",text=names,textposition="bottom center",name="SKEL ajustado"))
        for i,n in enumerate(names):
            fig.add_trace(go.Scatter3d(x=[T[i,0],after_xyz[i,0]],y=[T[i,1],after_xyz[i,1]],z=[T[i,2],after_xyz[i,2]],mode="lines",showlegend=False,hoverinfo="skip"))
        fig.update_layout(height=620,margin=dict(l=0,r=0,t=45,b=0),title="V110.2.4 · Frame semilla · XYZ objetivo vs SKEL",scene=dict(aspectmode="data"))
        st.plotly_chart(fig,use_container_width=True)
    except Exception as exc:
        st.caption(f"Visualización del fit no disponible: {exc}")

# V110.2.4 · HIERARCHICAL RETARGETING
# La pose SKEL deja de optimizar 46 q libres contra 15 landmarks.
# Sólo se activan DOF observables/razonablemente inferibles desde centros articulares;
# el resto queda neutral para impedir torsiones internas no determinadas por V104/V107.
_SKEL_Q_NAMES = [
    'pelvis_tilt','pelvis_list','pelvis_rotation',
    'hip_flexion_r','hip_adduction_r','hip_rotation_r','knee_angle_r','ankle_angle_r','subtalar_angle_r','mtp_angle_r',
    'hip_flexion_l','hip_adduction_l','hip_rotation_l','knee_angle_l','ankle_angle_l','subtalar_angle_l','mtp_angle_l',
    'lumbar_bending','lumbar_extension','lumbar_twist','thorax_bending','thorax_extension','thorax_twist',
    'head_bending','head_extension','head_twist',
    'scapula_abduction_r','scapula_elevation_r','scapula_upward_rot_r',
    'shoulder_r_x','shoulder_r_y','shoulder_r_z','elbow_flexion_r','pro_sup_r','wrist_flexion_r','wrist_deviation_r',
    'scapula_abduction_l','scapula_elevation_l','scapula_upward_rot_l',
    'shoulder_l_x','shoulder_l_y','shoulder_l_z','elbow_flexion_l','pro_sup_l','wrist_flexion_l','wrist_deviation_l'
]
_QI={n:i for i,n in enumerate(_SKEL_Q_NAMES)}
# DOF que sí pueden inferirse de los centros articulares disponibles.
_ACTIVE_GROUPS={
    'axial': [_QI[x] for x in ('lumbar_bending','lumbar_extension','thorax_bending','thorax_extension')],
    'lower': [_QI[x] for x in ('hip_flexion_r','hip_adduction_r','knee_angle_r','hip_flexion_l','hip_adduction_l','knee_angle_l')],
    'upper': [_QI[x] for x in ('shoulder_r_x','shoulder_r_y','shoulder_r_z','elbow_flexion_r','shoulder_l_x','shoulder_l_y','shoulder_l_z','elbow_flexion_l')],
}
_ACTIVE_Q=sorted(set(sum(_ACTIVE_GROUPS.values(),[])))
# Límites conservadores basados en los límites oficiales de SKEL donde están definidos,
# y márgenes de marcha clínica para los DOF sin límite publicado explícito.
_Q_LIMITS={
    _QI['hip_flexion_r']:(-1.35,1.35), _QI['hip_adduction_r']:(-0.65,0.65), _QI['knee_angle_r']:(0.0,2.30),
    _QI['hip_flexion_l']:(-1.35,1.35), _QI['hip_adduction_l']:(-0.65,0.65), _QI['knee_angle_l']:(0.0,2.30),
    _QI['lumbar_bending']:(-0.52,0.52), _QI['lumbar_extension']:(-0.70,0.70),
    _QI['thorax_bending']:(-0.70,0.70), _QI['thorax_extension']:(-0.70,0.70),
    _QI['shoulder_r_x']:(-1.75,1.75), _QI['shoulder_r_y']:(-1.57,1.57), _QI['shoulder_r_z']:(-1.75,1.75),
    _QI['elbow_flexion_r']:(0.0,2.30),
    _QI['shoulder_l_x']:(-1.75,1.75), _QI['shoulder_l_y']:(-1.57,1.57), _QI['shoulder_l_z']:(-1.75,1.75),
    _QI['elbow_flexion_l']:(0.0,2.30),
}

_STAGE_TARGETS={
    'axial': {'Hip','LHip','RHip','Neck','Head','LShoulder','RShoulder'},
    'lower': {'Hip','LHip','RHip','LKnee','RKnee','LAnkle','RAnkle'},
    'upper': {'Neck','LShoulder','RShoulder','LElbow','RElbow','LWrist','RWrist'},
    'all': set(JOINTS),
}

def _joint_index_map(model):
    names=[str(x) for x in getattr(model,'joints_name',[]) or []]
    return {_simple_name(n):i for i,n in enumerate(names)}

def _angle_np(a,b,c):
    u=np.asarray(a,float)-np.asarray(b,float); v=np.asarray(c,float)-np.asarray(b,float)
    den=max(np.linalg.norm(u)*np.linalg.norm(v),1e-9)
    return float(np.arccos(np.clip(np.dot(u,v)/den,-1.0,1.0)))

def _seed_hinge_angles_from_target(pose_np, target_map):
    p=np.asarray(pose_np,dtype=np.float32).copy()
    for side,hip,knee,ankle,qname in [
        ('R','RHip','RKnee','RAnkle','knee_angle_r'),('L','LHip','LKnee','LAnkle','knee_angle_l')]:
        if all(x in target_map for x in (hip,knee,ankle)):
            flex=max(0.0,min(2.30,float(np.pi-_angle_np(target_map[hip],target_map[knee],target_map[ankle]))))
            p[_QI[qname]]=flex
    for sh,el,wr,qname in [
        ('RShoulder','RElbow','RWrist','elbow_flexion_r'),('LShoulder','LElbow','LWrist','elbow_flexion_l')]:
        if all(x in target_map for x in (sh,el,wr)):
            flex=max(0.0,min(2.30,float(np.pi-_angle_np(target_map[sh],target_map[el],target_map[wr]))))
            p[_QI[qname]]=flex
    return p

def _apply_q_constraints(torch, pose):
    with torch.no_grad():
        # Todo DOF no observable vuelve exactamente a neutro en cada iteración.
        inactive=[i for i in range(int(pose.shape[1])) if i not in _ACTIVE_Q]
        if inactive:
            pose[:,inactive]=0.0
        for i,(lo,hi) in _Q_LIMITS.items():
            pose[:,i].clamp_(float(lo),float(hi))

def _mask_pose_grad(pose, active_indices):
    if pose.grad is None: return
    mask=np.zeros((pose.shape[1],),dtype=np.float32); mask[list(active_indices)]=1.0
    pose.grad.mul_(pose.grad.new_tensor(mask).reshape(1,-1))

def _target_tensor_for_rows(torch, target_df, rows, names_subset=None):
    tmap={r.joint:np.array([r.x,r.y,r.z],np.float32) for r in target_df.itertuples()}
    rr=[r for r in rows if names_subset is None or r[0] in names_subset]
    idx=torch.tensor([r[1] for r in rr],dtype=torch.long,device='cpu')
    tgt=torch.tensor(np.stack([tmap[r[0]] for r in rr]).astype(np.float32),dtype=torch.float32,device='cpu')
    return rr,idx,tgt,tmap

def _hierarchical_stage(torch, model, pose, rotvec, trans, fixed_scale, target_df, rows,
                        active_indices, target_names, betas, zero_trans, iterations=28, lr=0.02,
                        reference_pose=None, similarity_mode=False):
    rr,idx,tgt,_=_target_tensor_for_rows(torch,target_df,rows,target_names)
    if len(rr)<3: return
    pose.requires_grad_(True); rotvec.requires_grad_(True)
    params=[pose,rotvec]
    if not similarity_mode:
        trans.requires_grad_(True); params.append(trans)
    opt=torch.optim.Adam(params,lr=float(lr))
    ref=reference_pose.detach().clone() if reference_pose is not None else pose.detach().clone()
    active=list(active_indices)
    for _ in range(int(iterations)):
        opt.zero_grad(set_to_none=True)
        out=model(pose,betas,zero_trans,skelmesh=False)
        sel=out.joints[0].index_select(0,idx)
        if similarity_mode:
            pred,_,_,_=_similarity_to_target(torch,sel,tgt,rotvec)
        else:
            pred,_=_transform_joints_fixed(torch,sel,rotvec,fixed_scale,trans)
        data=torch.mean(torch.sum((pred-tgt)**2,dim=1))
        # El refinamiento puede moverse, pero no inventar torsiones grandes.
        reg=2.5e-3*torch.mean((pose[:,active]-ref[:,active])**2) if active else torch.zeros((),dtype=pose.dtype)
        loss=data+reg
        loss.backward()
        _mask_pose_grad(pose,active)
        torch.nn.utils.clip_grad_norm_(params,5.0)
        opt.step(); _apply_q_constraints(torch,pose)
        with torch.no_grad(): rotvec.clamp_(-3.14159,3.14159)
    pose.requires_grad_(False); rotvec.requires_grad_(False); trans.requires_grad_(False)

def _pose_safety_audit(model, joints_np, pose_np):
    names=[str(x) for x in getattr(model,'joints_name',[]) or []]
    m={_simple_name(n):i for i,n in enumerate(names)}; J=np.asarray(joints_np,float); p=np.asarray(pose_np,float)
    flags=[]
    inactive=np.array([p[i] for i in range(min(len(p),46)) if i not in _ACTIVE_Q],float)
    leak=float(np.nanmax(np.abs(inactive))) if inactive.size else 0.0
    if leak>1e-5: flags.append(f'DOF no observable fuera de neutro={leak:.3g}')
    hits=[]
    for i in _ACTIVE_Q:
        if i in _Q_LIMITS:
            lo,hi=_Q_LIMITS[i]
            if abs(float(p[i])-lo)<1e-3 or abs(float(p[i])-hi)<1e-3: hits.append(_SKEL_Q_NAMES[i])
    if hits: flags.append('límite: '+', '.join(hits[:5]))
    def ang(a,b,c):
        try: return float(np.degrees(_angle_np(J[m[_simple_name(a)]],J[m[_simple_name(b)]],J[m[_simple_name(c)]])))
        except Exception: return np.nan
    vals={'rodilla I':ang('left_hip','left_knee','left_ankle'),'rodilla D':ang('right_hip','right_knee','right_ankle'),
          'codo I':ang('left_shoulder','left_elbow','left_wrist'),'codo D':ang('right_shoulder','right_elbow','right_wrist')}
    for lab,a in vals.items():
        if np.isfinite(a) and (a<35 or a>181): flags.append(f'{lab}={a:.0f}°')
    return {'ok':not flags,'flags':flags,'inactive_q_leak':leak,'active_dof_count':len(_ACTIVE_Q),**vals}

def _fit_one_skel_frame(torch, model, target_df, max_iter=120):
    rows,joint_names=_resolve_skel_correspondence(model,target_df)
    if len(rows)<8: raise RuntimeError(f'Sólo se pudieron resolver {len(rows)} correspondencias SKEL↔XYZ; se requieren al menos 8. joints_name={joint_names}')
    all_rr,idx,tgt,target_map=_target_tensor_for_rows(torch,target_df,rows,None)
    betas=torch.zeros((1,int(model.num_betas)),dtype=torch.float32,device='cpu'); zero_trans=torch.zeros((1,3),dtype=torch.float32,device='cpu')
    pose_np=np.zeros((int(model.num_q_params),),np.float32); pose_np=_seed_hinge_angles_from_target(pose_np,target_map)
    pose=torch.tensor(pose_np,dtype=torch.float32).reshape(1,-1)
    rotvec=torch.zeros((3,),dtype=torch.float32); trans=torch.zeros((3,),dtype=torch.float32)
    # Antes: pose neutral con las bisagras inferidas, registrada por similitud.
    with torch.no_grad():
        J0=model(pose,betas,zero_trans,skelmesh=False).joints[0]; sel0=J0.index_select(0,idx)
        pred0,R0,s0,t0=_similarity_to_target(torch,sel0,tgt,rotvec)
        before=pred0.detach().cpu().numpy(); err_before=np.linalg.norm(before-tgt.cpu().numpy(),axis=1)
    # Jerarquía: eje corporal -> miembros inferiores -> miembros superiores -> micro-refinado conjunto.
    for stage,niter,lr in [('axial',30,0.020),('lower',42,0.020),('upper',42,0.018),('all',28,0.010)]:
        active=_ACTIVE_Q if stage=='all' else _ACTIVE_GROUPS[stage]
        names=_STAGE_TARGETS[stage]
        _hierarchical_stage(torch,model,pose,rotvec,trans,torch.tensor(1.0),target_df,rows,active,names,betas,zero_trans,
                            iterations=niter,lr=lr,reference_pose=pose.detach().clone(),similarity_mode=True)
    with torch.no_grad():
        J=model(pose,betas,zero_trans,skelmesh=False).joints[0]; sel=J.index_select(0,idx)
        pred,R,scale,trans2=_similarity_to_target(torch,sel,tgt,rotvec)
        all_after=(J @ R.T)*scale + trans2
        after=pred.cpu().numpy(); tgt_arr=tgt.cpu().numpy(); err_after=np.linalg.norm(after-tgt_arr,axis=1)
    return {'rows':rows,'joint_names':joint_names,'pose':pose.cpu().numpy()[0],'rotvec':rotvec.cpu().numpy(),
            'scale':float(scale.cpu()),'trans':trans2.cpu().numpy(),'target':tgt_arr,'before':before,'after':after,
            'all_after':all_after.cpu().numpy(),'rmse_before':float(np.sqrt(np.mean(err_before**2))),
            'rmse_after':float(np.sqrt(np.mean(err_after**2))),'errors_before':err_before,'errors_after':err_after,
            'history':[],'retargeting_mode':'hierarchical_16dof','active_q_names':[_SKEL_Q_NAMES[i] for i in _ACTIVE_Q]}

# V110.2.4 · propagación temporal jerárquica con 16 DOF activos.
def _target_df_for_frame(frame, frame_index):
    pts=_frame_points_from_frame(frame); return _target_csv(pts,frame_index)

def _transform_joints_fixed(torch, joints, rotvec, scale, trans):
    R=_rodrigues_torch(torch,rotvec); return (joints @ R.T)*scale+trans,R

def _fit_skel_sequence(torch, model, motion, seed_fit, start_index=0, iterations=16, progress_cb=None):
    frames=list((motion or {}).get('frames') or [])
    if not frames: raise RuntimeError('No hay frames V104/V107 para propagación temporal.')
    betas=torch.zeros((1,int(model.num_betas)),dtype=torch.float32); zero_trans=torch.zeros((1,3),dtype=torch.float32)
    fixed_scale=torch.tensor(float(seed_fit['scale']),dtype=torch.float32)
    prev_pose=torch.tensor(seed_fit['pose'],dtype=torch.float32).reshape(1,-1); _apply_q_constraints(torch,prev_pose)
    prev_rot=torch.tensor(seed_fit['rotvec'],dtype=torch.float32); prev_trans=torch.tensor(seed_fit['trans'],dtype=torch.float32)
    sequence=[]
    for fi in range(int(start_index),len(frames)):
        tdf=_target_df_for_frame(frames[fi],fi); rows,joint_names=_resolve_skel_correspondence(model,tdf)
        if len(rows)<8:
            sequence.append({'frame':fi+1,'status':'insufficient_landmarks','n_correspondences':len(rows)}); continue
        _,idx,tgt,tmap=_target_tensor_for_rows(torch,tdf,rows,None)
        pose_np=_seed_hinge_angles_from_target(prev_pose.cpu().numpy()[0],tmap)
        pose=torch.tensor(pose_np,dtype=torch.float32).reshape(1,-1); _apply_q_constraints(torch,pose)
        rotvec=prev_rot.clone(); trans=prev_trans.clone()
        if fi>int(start_index):
            # Cada grupo se ajusta sólo con los landmarks que realmente lo observan.
            for stage,niter,lr in [('axial',8,0.010),('lower',12,0.012),('upper',12,0.010),('all',8,0.006)]:
                active=_ACTIVE_Q if stage=='all' else _ACTIVE_GROUPS[stage]
                _hierarchical_stage(torch,model,pose,rotvec,trans,fixed_scale,tdf,rows,active,_STAGE_TARGETS[stage],betas,zero_trans,
                                    iterations=niter,lr=lr,reference_pose=prev_pose,similarity_mode=False)
        with torch.no_grad():
            J=model(pose,betas,zero_trans,skelmesh=False).joints[0]; sel=J.index_select(0,idx)
            pred,_=_transform_joints_fixed(torch,sel,rotvec,fixed_scale,trans); allj,_=_transform_joints_fixed(torch,J,rotvec,fixed_scale,trans)
            errors=torch.linalg.norm(pred-tgt,dim=1); rmse=float(torch.sqrt(torch.mean(errors*errors)).cpu())
            audit=_pose_safety_audit(model,allj.cpu().numpy(),pose.cpu().numpy()[0])
            sequence.append({'frame':fi+1,'status':'ok','n_correspondences':len(rows),'rmse':rmse,'anatomical_audit':audit,
                'retargeting_mode':'hierarchical_16dof','active_q_names':[_SKEL_Q_NAMES[i] for i in _ACTIVE_Q],
                'pose':pose.cpu().numpy()[0].astype(float).tolist(),'rotvec':rotvec.cpu().numpy().astype(float).tolist(),
                'trans':trans.cpu().numpy().astype(float).tolist(),'joints':allj.cpu().numpy().astype(float).tolist()})
            prev_pose=pose.clone(); prev_rot=rotvec.clone(); prev_trans=trans.clone()
        if progress_cb: progress_cb(fi+1,len(frames),rmse)
    return {'version':'110.2.4','retargeting_mode':'hierarchical_16dof','scale':float(fixed_scale.cpu()),
            'active_q_names':[_SKEL_Q_NAMES[i] for i in _ACTIVE_Q],
            'joint_names':[str(x) for x in getattr(model,'joints_name',[])],'frames':sequence}

def _plot_skel_sequence_animation(seq):
    ok=[f for f in seq.get("frames",[]) if f.get("status")=="ok" and f.get("joints")]
    if not ok:
        st.warning("No hay frames SKEL válidos para animar."); return
    try:
        import plotly.graph_objects as go
        names=[str(x) for x in seq.get("joint_names",[])]
        norm={_simple_name(n):i for i,n in enumerate(names)}
        edge_names=[
            ("pelvis","left_hip"),("pelvis","right_hip"),("pelvis","spine1"),
            ("left_hip","left_knee"),("left_knee","left_ankle"),("left_ankle","left_foot"),
            ("right_hip","right_knee"),("right_knee","right_ankle"),("right_ankle","right_foot"),
            ("spine1","spine2"),("spine2","spine3"),("spine3","neck"),("neck","head"),
            ("neck","left_collar"),("left_collar","left_shoulder"),("left_shoulder","left_elbow"),("left_elbow","left_wrist"),
            ("neck","right_collar"),("right_collar","right_shoulder"),("right_shoulder","right_elbow"),("right_elbow","right_wrist"),
        ]
        edges=[]
        for a,b in edge_names:
            ia=norm.get(_simple_name(a)); ib=norm.get(_simple_name(b))
            if ia is not None and ib is not None: edges.append((ia,ib))
        all_xyz=np.concatenate([np.asarray(f["joints"],float) for f in ok],axis=0)
        mins=np.nanmin(all_xyz,axis=0); maxs=np.nanmax(all_xyz,axis=0); span=np.maximum(maxs-mins,1e-3); pad=0.08*span
        def traces(fr):
            J=np.asarray(fr["joints"],float)
            xs=[]; ys=[]; zs=[]
            for a,b in edges:
                xs += [J[a,0],J[b,0],None]; ys += [J[a,1],J[b,1],None]; zs += [J[a,2],J[b,2],None]
            return [
                go.Scatter3d(x=xs,y=ys,z=zs,mode="lines",name="SKEL",showlegend=False),
                go.Scatter3d(x=J[:,0],y=J[:,1],z=J[:,2],mode="markers",name="Joints SKEL"),
            ]
        anim_frames=[go.Frame(data=traces(f),name=str(f["frame"])) for f in ok]
        fig=go.Figure(data=traces(ok[0]),frames=anim_frames)
        steps=[dict(method="animate",args=[[str(f["frame"])],{"mode":"immediate","frame":{"duration":60,"redraw":True},"transition":{"duration":0}}],label=str(f["frame"])) for f in ok]
        fig.update_layout(
            height=680,margin=dict(l=0,r=0,t=45,b=0),title="V110.2.4 · SKEL · marcha propagada temporalmente",
            scene=dict(aspectmode="data",xaxis=dict(range=[mins[0]-pad[0],maxs[0]+pad[0]]),yaxis=dict(range=[mins[1]-pad[1],maxs[1]+pad[1]]),zaxis=dict(range=[mins[2]-pad[2],maxs[2]+pad[2]])),
            updatemenus=[dict(type="buttons",showactive=False,buttons=[dict(label="▶ Reproducir",method="animate",args=[None,{"fromcurrent":True,"frame":{"duration":60,"redraw":True},"transition":{"duration":0}}]),dict(label="⏸ Pausa",method="animate",args=[[None],{"mode":"immediate","frame":{"duration":0,"redraw":False}}])])],
            sliders=[dict(active=0,currentvalue={"prefix":"Frame "},steps=steps,pad={"t":35})]
        )
        st.plotly_chart(fig,use_container_width=True)
    except Exception as exc:
        st.warning(f"La secuencia se calculó, pero la animación 3D no pudo mostrarse: {type(exc).__name__}: {exc}")




def _plot_simplified_xyz_animation(motion):
    """Recupera el vídeo/animación 3D simplificado no calibrado V104/V107 como referencia visual."""
    frames=list((motion or {}).get('frames') or [])
    if not frames: return
    try:
        import plotly.graph_objects as go
        edge_names=[('Hip','LHip'),('Hip','RHip'),('LHip','LKnee'),('LKnee','LAnkle'),('RHip','RKnee'),('RKnee','RAnkle'),
                    ('Hip','Neck'),('Neck','Head'),('Neck','LShoulder'),('LShoulder','LElbow'),('LElbow','LWrist'),
                    ('Neck','RShoulder'),('RShoulder','RElbow'),('RElbow','RWrist')]
        payload=[]
        for i,f in enumerate(frames):
            P=_frame_points_from_frame(f)
            names=[n for n in JOINTS if n in P]
            pts=np.asarray([P[n] for n in names],float) if names else np.zeros((0,3))
            ex=[];ey=[];ez=[]
            for a,b in edge_names:
                if a in P and b in P:
                    ex += [P[a][0],P[b][0],None]; ey += [P[a][1],P[b][1],None]; ez += [P[a][2],P[b][2],None]
            traces=[go.Scatter3d(x=ex,y=ey,z=ez,mode='lines',line=dict(width=5),showlegend=False,hoverinfo='skip')]
            traces.append(go.Scatter3d(x=pts[:,0] if len(pts) else [],y=pts[:,1] if len(pts) else [],z=pts[:,2] if len(pts) else [],
                                       mode='markers+text',text=names,textposition='top center',marker=dict(size=5),showlegend=False))
            payload.append((i,traces))
        fig=go.Figure(data=payload[0][1],frames=[go.Frame(data=t,name=str(i+1)) for i,t in payload])
        fig.update_layout(height=600,margin=dict(l=0,r=0,t=45,b=0),title='V110.2.4 · Vídeo 3D simplificado V104/V107 · no calibrado',
            scene=dict(aspectmode='data'),updatemenus=[dict(type='buttons',showactive=False,buttons=[
                dict(label='▶ Reproducir',method='animate',args=[None,dict(frame=dict(duration=60,redraw=True),transition=dict(duration=0),fromcurrent=True)]),
                dict(label='⏸ Pausa',method='animate',args=[[None],dict(frame=dict(duration=0,redraw=False),mode='immediate')])])],
            sliders=[dict(active=0,currentvalue=dict(prefix='Frame '),steps=[dict(method='animate',label=str(i+1),args=[[str(i+1)],dict(mode='immediate',frame=dict(duration=0,redraw=True),transition=dict(duration=0))]) for i in range(len(payload))])])
        st.plotly_chart(fig,use_container_width=True)
    except Exception as exc:
        st.caption(f'Vídeo 3D simplificado no disponible: {exc}')

# V110.2.4 · SKEL MESH WALKER: malla corporal real `skin_verts` sobre la secuencia temporal validada.
def _skin_faces_numpy(model):
    """Recupera la topología fija de la malla corporal SKEL.

    La API oficial de SKEL usa `model.skin_f`; se conservan fallbacks tolerantes
    por si una revisión futura expone el mismo tensor con otro nombre.
    """
    for name in ("skin_f", "skin_faces", "faces_skin", "faces"):
        f=getattr(model,name,None)
        if f is None:
            continue
        try:
            if hasattr(f,"detach"):
                f=f.detach().cpu().numpy()
            else:
                f=np.asarray(f)
            f=np.asarray(f,dtype=np.int32)
            if f.ndim==3 and f.shape[0]==1:
                f=f[0]
            if f.ndim==2 and f.shape[1]>=3:
                return f[:,:3].copy(), name
        except Exception:
            pass
    raise RuntimeError("SKEL ha devuelto skin_verts, pero no se encontró la topología triangular de la piel (esperado: model.skin_f).")

def _build_skel_skin_sequence(torch, model, seq, progress_cb=None):
    """Evalúa `skin_verts` para cada pose ya ajustada sin volver a optimizar la marcha.

    La identidad se mantiene fija (betas=0, igual que durante el fitting), y a cada
    malla se aplica exactamente la escala/orientación/traslación guardada en V110.2.0/2.1.
    """
    ok=[f for f in (seq or {}).get("frames",[]) if f.get("status")=="ok" and f.get("pose")]
    if not ok:
        raise RuntimeError("No hay poses SKEL válidas para generar la malla corporal.")
    faces,face_source=_skin_faces_numpy(model)
    betas=torch.zeros((1,int(model.num_betas)),dtype=torch.float32,device="cpu")
    zero_trans=torch.zeros((1,3),dtype=torch.float32,device="cpu")
    seq_scale=float(seq.get("scale",1.0))
    if not np.isfinite(seq_scale) or seq_scale<=0:
        raise RuntimeError(f"Escala de secuencia no válida: {seq_scale}")
    scale=torch.tensor(seq_scale,dtype=torch.float32,device="cpu")
    verts=[]; joints=[]; frame_ids=[]
    total=len(ok)
    with torch.no_grad():
        for k,fr in enumerate(ok,1):
            pose=torch.tensor(fr["pose"],dtype=torch.float32,device="cpu").reshape(1,-1)
            rot=torch.tensor(fr.get("rotvec",[0,0,0]),dtype=torch.float32,device="cpu")
            trans=torch.tensor(fr.get("trans",[0,0,0]),dtype=torch.float32,device="cpu")
            out=model(pose,betas,zero_trans,skelmesh=False)
            skin=getattr(out,"skin_verts",None)
            if skin is None:
                raise RuntimeError(f"Frame {fr.get('frame')}: SKEL no devolvió skin_verts.")
            V=skin[0]
            Vt,_=_transform_joints_fixed(torch,V,rot,scale,trans)
            verts.append(Vt.detach().cpu().numpy().astype(np.float32))
            # Reusar joints temporales validados si existen; evita otro convenio geométrico.
            if fr.get("joints") is not None:
                joints.append(np.asarray(fr["joints"],dtype=np.float32))
            else:
                J=getattr(out,"joints",None)
                if J is not None:
                    Jt,_=_transform_joints_fixed(torch,J[0],rot,scale,trans)
                    joints.append(Jt.detach().cpu().numpy().astype(np.float32))
            frame_ids.append(int(fr.get("frame",k)))
            if progress_cb:
                progress_cb(k,total,int(V.shape[0]))
    V=np.stack(verts,axis=0)
    J=np.stack(joints,axis=0) if len(joints)==len(verts) else None
    return {
        "version":"110.2.4",
        "frame_ids":np.asarray(frame_ids,dtype=np.int16),
        "vertices":V,
        "faces":faces.astype(np.int32),
        "joints":J,
        "joint_names":[str(x) for x in seq.get("joint_names",[])],
        "scale":float(seq.get("scale",1.0)),
        "betas":np.zeros((int(model.num_betas),),dtype=np.float32),
        "face_source":face_source,
        "source_sequence_version":str(seq.get("version","")),
        "source_sequence_scale":float(seq_scale),
    }

def _mesh_sequence_npz_bytes(mesh_seq):
    buf=io.BytesIO()
    payload={
        "version":np.asarray([str(mesh_seq.get("version","110.2.4"))]),
        "frame_ids":mesh_seq["frame_ids"],
        "vertices":mesh_seq["vertices"],
        "faces":mesh_seq["faces"],
        "scale":np.asarray([mesh_seq.get("scale",1.0)],dtype=np.float32),
        "betas":mesh_seq["betas"],
        "joint_names":np.asarray(mesh_seq.get("joint_names",[]),dtype=str),
        "source_sequence_version":np.asarray([str(mesh_seq.get("source_sequence_version",""))]),
        "source_sequence_scale":np.asarray([mesh_seq.get("source_sequence_scale",mesh_seq.get("scale",1.0))],dtype=np.float32),
    }
    if mesh_seq.get("joints") is not None:
        payload["joints"]=mesh_seq["joints"]
    np.savez_compressed(buf,**payload)
    return buf.getvalue()

def _plot_skel_mesh_walker(mesh_seq):
    """Visor Plotly 3D orbitable: malla corporal SKEL + joints, Play/Pausa y velocidades."""
    try:
        import plotly.graph_objects as go
        V=np.asarray(mesh_seq["vertices"],dtype=np.float32)
        F=np.asarray(mesh_seq["faces"],dtype=np.int32)
        frame_ids=[int(x) for x in np.asarray(mesh_seq["frame_ids"]).tolist()]
        J=mesh_seq.get("joints")
        J=np.asarray(J,dtype=np.float32) if J is not None else None
        if V.ndim!=3 or V.shape[0]<1 or F.ndim!=2:
            raise RuntimeError("Dimensiones de malla no válidas.")
        # Rango fijo durante toda la marcha: evita zoom/reencuadre frame a frame.
        mins=np.nanmin(V.reshape(-1,3),axis=0); maxs=np.nanmax(V.reshape(-1,3),axis=0)
        span=np.maximum(maxs-mins,1e-3); pad=np.maximum(0.05*span,0.02)
        names=[str(x) for x in mesh_seq.get("joint_names",[])]
        norm={_simple_name(n):i for i,n in enumerate(names)}
        edge_names=[
            ("pelvis","left_hip"),("pelvis","right_hip"),("pelvis","spine1"),
            ("left_hip","left_knee"),("left_knee","left_ankle"),("left_ankle","left_foot"),
            ("right_hip","right_knee"),("right_knee","right_ankle"),("right_ankle","right_foot"),
            ("spine1","spine2"),("spine2","spine3"),("spine3","neck"),("neck","head"),
            ("neck","left_shoulder"),("left_shoulder","left_elbow"),("left_elbow","left_wrist"),
            ("neck","right_shoulder"),("right_shoulder","right_elbow"),("right_elbow","right_wrist"),
        ]
        edges=[(norm[_simple_name(a)],norm[_simple_name(b)]) for a,b in edge_names if _simple_name(a) in norm and _simple_name(b) in norm]
        def joint_trace(k):
            if J is None or k>=len(J):
                return go.Scatter3d(x=[],y=[],z=[],mode="lines+markers",name="Joints",visible=False)
            Q=J[k]; xs=[]; ys=[]; zs=[]
            for a,b in edges:
                xs += [Q[a,0],Q[b,0],None]; ys += [Q[a,1],Q[b,1],None]; zs += [Q[a,2],Q[b,2],None]
            return go.Scatter3d(x=xs,y=ys,z=zs,mode="lines+markers",name="Joints SKEL")
        def mesh_trace(k,include_faces=True):
            kw=dict(x=V[k,:,0],y=V[k,:,1],z=V[k,:,2],name="Malla corporal SKEL",opacity=0.88,flatshading=False,lighting=dict(ambient=0.55,diffuse=0.75,specular=0.15,roughness=0.75))
            if include_faces:
                kw.update(i=F[:,0],j=F[:,1],k=F[:,2])
            return go.Mesh3d(**kw)
        data=[mesh_trace(0,True),joint_trace(0)]
        anim=[]
        for k,fid in enumerate(frame_ids):
            # Los frames actualizan sólo XYZ; la topología triangular se hereda del trace inicial.
            anim.append(go.Frame(name=str(fid),data=[mesh_trace(k,False),joint_trace(k)],traces=[0,1]))
        steps=[dict(method="animate",args=[[str(fid)],{"mode":"immediate","frame":{"duration":0,"redraw":True},"transition":{"duration":0}}],label=str(fid)) for fid in frame_ids]
        fig=go.Figure(data=data,frames=anim)
        fig.update_layout(
            height=760,margin=dict(l=0,r=0,t=50,b=0),title="V110.2.4 · SKEL MESH WALKER · marcha anatómica 3D",
            scene=dict(aspectmode="data",xaxis=dict(range=[mins[0]-pad[0],maxs[0]+pad[0]]),yaxis=dict(range=[mins[1]-pad[1],maxs[1]+pad[1]]),zaxis=dict(range=[mins[2]-pad[2],maxs[2]+pad[2]])),
            updatemenus=[dict(type="buttons",direction="left",showactive=False,x=0.0,y=1.08,buttons=[
                dict(label="▶ 0.5×",method="animate",args=[None,{"fromcurrent":True,"frame":{"duration":120,"redraw":True},"transition":{"duration":0}}]),
                dict(label="▶ 1×",method="animate",args=[None,{"fromcurrent":True,"frame":{"duration":60,"redraw":True},"transition":{"duration":0}}]),
                dict(label="▶ 2×",method="animate",args=[None,{"fromcurrent":True,"frame":{"duration":30,"redraw":True},"transition":{"duration":0}}]),
                dict(label="⏸ Pausa",method="animate",args=[[None],{"mode":"immediate","frame":{"duration":0,"redraw":False},"transition":{"duration":0}}]),
            ])],
            sliders=[dict(active=0,currentvalue={"prefix":"Frame "},steps=steps,pad={"t":40})],
            legend=dict(orientation="h")
        )
        st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":True})
    except Exception as exc:
        st.warning(f"La malla SKEL se calculó, pero el visor 3D no pudo mostrarse: {type(exc).__name__}: {exc}")


# V110.2.4 · CALIBRACIÓN EMPÍRICA DE LOS DOF SKEL
# No presupone equivalencias biomecánicas para q0..q45. Cada q se perturba
# alrededor de la postura neutra y se observa qué joints reales mueve el modelo.
def _calibrate_skel_dofs(torch, model, delta=0.12, progress_cb=None):
    qn=int(model.num_q_params)
    betas=torch.zeros((1,int(model.num_betas)),dtype=torch.float32,device='cpu')
    zero_trans=torch.zeros((1,3),dtype=torch.float32,device='cpu')
    names=[str(x) for x in getattr(model,'joints_name',[]) or []]
    pose0=torch.zeros((1,qn),dtype=torch.float32,device='cpu')
    with torch.no_grad():
        base=model(pose0,betas,zero_trans,skelmesh=False).joints[0].detach().cpu().numpy().astype(np.float64)
    rows=[]; d=float(delta)
    for qi in range(qn):
        pp=pose0.clone(); pm=pose0.clone(); pp[0,qi]=d; pm[0,qi]=-d
        with torch.no_grad():
            jp=model(pp,betas,zero_trans,skelmesh=False).joints[0].detach().cpu().numpy().astype(np.float64)
            jm=model(pm,betas,zero_trans,skelmesh=False).joints[0].detach().cpu().numpy().astype(np.float64)
        deriv=(jp-jm)/(2.0*d)
        mag=np.linalg.norm(deriv,axis=1); order=np.argsort(-mag)
        mx=float(mag[order[0]]) if len(order) else 0.0
        moved=[int(i) for i in order if mag[i] >= max(mx*0.20,1e-5)][:8]
        top=[f"{names[i] if i < len(names) else i}:{mag[i]:.4f}" for i in order[:5]]
        if len(order):
            v=deriv[order[0]]; ax=int(np.argmax(np.abs(v))); axis='XYZ'[ax]; sign='+' if float(v[ax])>=0 else '-'
        else: axis='—'; sign='—'
        rows.append({'q_index':qi,'sensibilidad_max_joint_u_por_rad':mx,
                     'joint_mas_sensible':names[order[0]] if len(order) and order[0] < len(names) else '—',
                     'eje_global_dominante_top_joint':axis,'signo_top_joint':sign,
                     'joints_afectados_20pct':', '.join(names[i] if i < len(names) else str(i) for i in moved),
                     'top5_joint_sensitivity':'; '.join(top),'efecto_detectable':bool(mx>1e-5)})
        if progress_cb: progress_cb(qi+1,qn,mx)
    return pd.DataFrame(rows), base

def _dof_calibration_json_bytes(df, delta, model):
    payload={'version':'110.2.4','method':'empirical central finite-difference around neutral pose',
             'delta_rad':float(delta),'num_q_params':int(model.num_q_params),
             'joint_names':[str(x) for x in getattr(model,'joints_name',[]) or []],
             'warning':'Los nombres biomecanicos previos de q no se asumen. La tabla describe el efecto observado del modelo privado.',
             'dofs':df.to_dict(orient='records')}
    return json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')

def _skel_edges_from_names(names):
    norm={_simple_name(n):i for i,n in enumerate(names)}
    edge_names=[('pelvis','left_hip'),('pelvis','right_hip'),('pelvis','spine1'),('left_hip','left_knee'),
        ('left_knee','left_ankle'),('left_ankle','left_foot'),('right_hip','right_knee'),('right_knee','right_ankle'),
        ('right_ankle','right_foot'),('spine1','spine2'),('spine2','spine3'),('spine3','neck'),('neck','head'),
        ('neck','left_shoulder'),('left_shoulder','left_elbow'),('left_elbow','left_wrist'),('neck','right_shoulder'),
        ('right_shoulder','right_elbow'),('right_elbow','right_wrist')]
    return [(norm[_simple_name(a)],norm[_simple_name(b)]) for a,b in edge_names if _simple_name(a) in norm and _simple_name(b) in norm]

def _plot_xyz_static(points,title,ranges=None,camera=None):
    import plotly.graph_objects as go
    links=[('LShoulder','RShoulder'),('LShoulder','LElbow'),('LElbow','LWrist'),('RShoulder','RElbow'),('RElbow','RWrist'),
           ('LShoulder','LHip'),('RShoulder','RHip'),('LHip','RHip'),('LHip','LKnee'),('LKnee','LAnkle'),('RHip','RKnee'),
           ('RKnee','RAnkle'),('Neck','LShoulder'),('Neck','RShoulder'),('Neck','Head')]
    fig=go.Figure()
    for a,b in links:
        if a in points and b in points:
            A=np.asarray(points[a],float); B=np.asarray(points[b],float)
            fig.add_trace(go.Scatter3d(x=[A[0],B[0]],y=[A[1],B[1]],z=[A[2],B[2]],mode='lines',showlegend=False,hoverinfo='skip'))
    labs=[j for j in JOINTS if j in points]
    if labs:
        P=np.asarray([points[j] for j in labs],float)
        fig.add_trace(go.Scatter3d(x=P[:,0],y=P[:,1],z=P[:,2],mode='markers',text=labs,name='XYZ V104/V107'))
    scene=dict(aspectmode='data')
    if ranges is not None: scene.update(xaxis=dict(range=ranges[0]),yaxis=dict(range=ranges[1]),zaxis=dict(range=ranges[2]))
    if camera is not None: scene['camera']=camera
    fig.update_layout(height=500,margin=dict(l=0,r=0,t=42,b=0),title=title,scene=scene,showlegend=False)
    return fig

def _plot_joints_static(J,names,title,target_points=None,ranges=None,camera=None):
    import plotly.graph_objects as go
    J=np.asarray(J,float); edges=_skel_edges_from_names(names); xs=[];ys=[];zs=[]
    for a,b in edges: xs += [J[a,0],J[b,0],None]; ys += [J[a,1],J[b,1],None]; zs += [J[a,2],J[b,2],None]
    fig=go.Figure([go.Scatter3d(x=xs,y=ys,z=zs,mode='lines+markers',name='Joints SKEL')])
    if target_points:
        norm={_simple_name(n):i for i,n in enumerate(names)}
        for target,cands in _SKEL_TARGET_CANDIDATES.items():
            if target not in target_points: continue
            ji=next((norm[_simple_name(c)] for c in cands if _simple_name(c) in norm),None)
            if ji is not None:
                T=np.asarray(target_points[target],float); S=J[ji]
                fig.add_trace(go.Scatter3d(x=[T[0],S[0]],y=[T[1],S[1]],z=[T[2],S[2]],mode='lines',showlegend=False,hoverinfo='skip'))
    scene=dict(aspectmode='data')
    if ranges is not None: scene.update(xaxis=dict(range=ranges[0]),yaxis=dict(range=ranges[1]),zaxis=dict(range=ranges[2]))
    if camera is not None: scene['camera']=camera
    fig.update_layout(height=500,margin=dict(l=0,r=0,t=42,b=0),title=title,scene=scene,showlegend=False)
    return fig

def _plot_mesh_static(V,F,title,J=None,names=None,ranges=None,camera=None):
    import plotly.graph_objects as go
    V=np.asarray(V,float); F=np.asarray(F,int)
    fig=go.Figure([go.Mesh3d(x=V[:,0],y=V[:,1],z=V[:,2],i=F[:,0],j=F[:,1],k=F[:,2],opacity=0.82,name='SKEL skin',flatshading=False)])
    if J is not None and names:
        J=np.asarray(J,float); xs=[];ys=[];zs=[]
        for a,b in _skel_edges_from_names(names): xs += [J[a,0],J[b,0],None]; ys += [J[a,1],J[b,1],None]; zs += [J[a,2],J[b,2],None]
        fig.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode='lines+markers',name='Joints'))
    scene=dict(aspectmode='data')
    if ranges is not None: scene.update(xaxis=dict(range=ranges[0]),yaxis=dict(range=ranges[1]),zaxis=dict(range=ranges[2]))
    if camera is not None: scene['camera']=camera
    fig.update_layout(height=500,margin=dict(l=0,r=0,t=42,b=0),title=title,scene=scene,showlegend=False)
    return fig

def _side_by_side_validation(motion,seq,mesh_seq):
    ok=[x for x in (seq or {}).get('frames',[]) if x.get('status')=='ok' and x.get('joints') is not None]
    if not ok: return
    fmap={int(x.get('frame')):x for x in ok}
    mesh_ids=[int(x) for x in np.asarray(mesh_seq.get('frame_ids',[])).tolist()] if isinstance(mesh_seq,dict) else []
    common=[f for f in sorted(fmap) if (not mesh_ids or f in mesh_ids)]
    if not common: return
    fid=st.slider('Frame sincronizado para validación',min_value=min(common),max_value=max(common),value=common[0],step=1,key='v110_2_4_sync_frame')
    if fid not in fmap: fid=min(common,key=lambda x:abs(x-fid))
    fr=fmap[fid]; mframes=list((motion or {}).get('frames') or [])
    points=_frame_points_from_frame(mframes[max(0,min(len(mframes)-1,fid-1))]) if mframes else {}
    J=np.asarray(fr['joints'],float); names=[str(x) for x in seq.get('joint_names',[])]
    vals=[]
    if points: vals.extend(np.asarray(list(points.values()),float).reshape(-1,3).tolist())
    vals.extend(J.tolist()); V=F=None
    if isinstance(mesh_seq,dict) and fid in mesh_ids:
        mi=mesh_ids.index(fid); V=np.asarray(mesh_seq['vertices'][mi],float); F=np.asarray(mesh_seq['faces'],int)
        vals.extend(np.percentile(V,[2,98],axis=0).tolist())
    A=np.asarray(vals,float); mn=np.nanmin(A,axis=0); mx=np.nanmax(A,axis=0); sp=np.maximum(mx-mn,0.2); pad=0.08*sp
    ranges=[(float(mn[i]-pad[i]),float(mx[i]+pad[i])) for i in range(3)]
    cam=dict(eye=dict(x=1.45,y=1.45,z=1.05),up=dict(x=0,y=0,z=1))
    c1,c2,c3=st.columns(3)
    with c1: st.plotly_chart(_plot_xyz_static(points,f'Frame {fid} · XYZ simplificado',ranges,cam),use_container_width=True,key=f'v124_xyz_{fid}')
    with c2: st.plotly_chart(_plot_joints_static(J,names,f'Frame {fid} · SKEL joints',points,ranges,cam),use_container_width=True,key=f'v124_joints_{fid}')
    with c3:
        if V is not None: st.plotly_chart(_plot_mesh_static(V,F,f'Frame {fid} · SKEL mesh',J,names,ranges,cam),use_container_width=True,key=f'v124_mesh_{fid}')
        else: st.info('Genera primero la malla SKEL para completar la tercera columna.')
    rows=[]; norm={_simple_name(n):i for i,n in enumerate(names)}
    for target,cands in _SKEL_TARGET_CANDIDATES.items():
        if target not in points: continue
        ji=next((norm[_simple_name(c)] for c in cands if _simple_name(c) in norm),None)
        if ji is not None: rows.append({'landmark':target,'skel_joint':names[ji],'error_3D':float(np.linalg.norm(np.asarray(points[target],float)-J[ji]))})
    if rows:
        edf=pd.DataFrame(rows).sort_values('error_3D',ascending=False); a,b,c=st.columns(3)
        a.metric('Error medio frame',f"{edf['error_3D'].mean():.4f}"); b.metric('Error máximo frame',f"{edf['error_3D'].max():.4f}"); c.metric('Landmark peor',str(edf.iloc[0]['landmark']))
        with st.expander('Errores XYZ ↔ SKEL del frame sincronizado',expanded=False): st.dataframe(edf,use_container_width=True,hide_index=True)

def render_skel_poc_panel(motion):
    frames=list((motion or {}).get("frames") or [])
    if not frames:
        st.warning("No hay secuencia V104/V107 disponible para construir el frame objetivo de SKEL.")
        return

    best_i, pts, score = _select_best_frame(motion)
    df = _target_csv(pts, best_i)
    raw_count = len(_frame_points_from_frame(frames[best_i])) if frames else 0

    st.success(f"Motor cinemático disponible: {len(frames)} frames. V110 usa el primer frame con cobertura articular suficiente como puerta de validación antes de animar SKEL.")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Frames V104/V107",len(frames))
    c2.metric("Landmarks objetivo",len(df))
    c3.metric("Frame seleccionado",f"{best_i+1}/{len(frames)}")
    c4.metric("SKEL","entrada XYZ")

    if len(df) == 0:
        st.error("V109.1 sigue sin encontrar landmarks compatibles dentro del payload V104/V107.")
        st.write("Claves presentes en el frame seleccionado:", list((frames[best_i].get("joints") or {}).keys())[:40])
        return
    elif len(df) < 10:
        st.warning(f"Sólo se han recuperado {len(df)} landmarks objetivo. El CSV es utilizable para diagnóstico, pero todavía no para un ajuste SKEL fiable.")
    else:
        st.info(f"Puente V104/V107 → SKEL recuperado: {len(df)} landmarks objetivo de {raw_count} puntos XYZ disponibles en el frame {best_i+1}.")

    st.download_button("⬇️ Frame objetivo V110 (CSV)",df.to_csv(index=False).encode("utf-8-sig"),
                       "V110_1_2_SKEL_target_frame.csv","text/csv",use_container_width=True)
    st.caption("Este CSV contiene las coordenadas XYZ que se usarán para el ajuste articular. Los centros derivados están identificados y no modifican ninguna métrica clínica.")

    _plot_frame(df)
    with st.expander("Ver coordenadas XYZ del frame objetivo", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Diagnóstico geométrico previo al fitting: no altera datos ni métricas clínicas.
    P={r.joint:np.array([r.x,r.y,r.z],dtype=float) for r in df.itertuples()}
    def dist(a,b):
        return float(np.linalg.norm(P[a]-P[b])) if a in P and b in P else float("nan")
    segs={
        "Pelvis L-R":dist("LHip","RHip"),
        "Fémur L":dist("LHip","LKnee"), "Fémur R":dist("RHip","RKnee"),
        "Tibia L":dist("LKnee","LAnkle"), "Tibia R":dist("RKnee","RAnkle"),
        "Húmero L":dist("LShoulder","LElbow"), "Húmero R":dist("RShoulder","RElbow"),
        "Antebrazo L":dist("LElbow","LWrist"), "Antebrazo R":dist("RElbow","RWrist"),
    }
    arr=df[["x","y","z"]].to_numpy(float)
    span=np.nanmax(arr,axis=0)-np.nanmin(arr,axis=0)
    st.markdown("**Control geométrico previo al fit**")
    q1,q2,q3=st.columns(3)
    q1.metric("Landmarks válidos",len(df))
    q2.metric("Extensión XYZ máx.",f"{float(np.max(span)):.3f}")
    finite=[v for v in segs.values() if np.isfinite(v) and v>0]
    q3.metric("Segmentos evaluables",len(finite))
    with st.expander("Longitudes del frame objetivo",expanded=False):
        st.dataframe(pd.DataFrame([{"segmento":k,"longitud_unidades_XYZ":v} for k,v in segs.items()]),use_container_width=True,hide_index=True)

    st.markdown("**Modelo SKEL privado · runtime V110.2.4 CPU + DOF Calibration + Side-by-Side + Mesh Walker**")
    st.caption("El puente XYZ ya está validado. Para que V110 genere y ajuste la malla esquelética SKEL real debes aportar tu ZIP oficial con `skel_male.pkl` o `skel_female.pkl`.")
    bundle=st.file_uploader("ZIP privado con los archivos de modelo SKEL descargados por ti desde el portal oficial",type=["zip"],key="v110_1_skel_private_bundle",help="No se guarda en Supabase ni se incorpora a la exportación de PhysioSentinel.")
    if bundle is None:
        st.info("Entrada articular preparada: 15 landmarks. Falta únicamente el modelo SKEL privado para ejecutar el ajuste anatómico real de este frame. V110 no sustituye SKEL por una malla falsa.")
        return
    raw=bundle.getvalue(); audit=_inspect_private_bundle(raw)
    if not audit.get("valid_zip"):
        st.error("El archivo aportado no es un ZIP SKEL válido."); return
    st.write({"skel_male.pkl":audit["has_male"],"skel_female.pkl":audit["has_female"]})
    if not (audit["has_male"] or audit["has_female"]):
        st.error("No encuentro skel_male.pkl ni skel_female.pkl en el ZIP. No se ejecuta ningún modelo."); return
    # V110.1.6: runtime SKEL CPU aislado + modelo privado extraído sólo a /tmp.
    # No se toca el venv administrado, NumPy, OpenSim ni el stack gráfico ModernGL.
    def _import_or_install_skel_cpu():
        try:
            import torch as _torch
            from skel.skel_model import SKEL as _SKEL  # type: ignore
            return _torch, _SKEL, None
        except Exception as first_exc:
            try:
                # Streamlit Cloud no permite escribir de forma fiable en el site-packages
                # del venv durante la ejecución. Instalamos SKEL en un target temporal
                # escribible, igual que el aislamiento probado de OpenCV V86.6.
                url = "git+https://github.com/MarilynKeller/SKEL.git@c32cf16581295bff19399379efe5b776d707cd95"
                target = Path(tempfile.gettempdir()) / "physiosentinel_skel_cpu_v110_1_7"
                marker = target / ".ready"
                target.mkdir(parents=True, exist_ok=True)
                if str(target) not in sys.path:
                    sys.path.insert(0, str(target))
                if not marker.exists():
                    cmd = [sys.executable, "-m", "pip", "install", "--no-deps",
                           "--disable-pip-version-check", "--no-cache-dir",
                           "--target", str(target), url]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                    if proc.returncode != 0:
                        tail = (proc.stderr or proc.stdout or "")[-4000:]
                        return None, None, f"Instalación SKEL aislada falló ({proc.returncode}):\n{tail}"
                    marker.write_text("ok", encoding="utf-8")
                importlib.invalidate_caches()
                # Evita conservar un import parcial fallido anterior al instalar.
                for name in list(sys.modules):
                    if name == "skel" or name.startswith("skel."):
                        sys.modules.pop(name, None)
                import torch as _torch
                from skel.skel_model import SKEL as _SKEL  # type: ignore
                return _torch, _SKEL, None
            except Exception as second_exc:
                return None, None, f"Import inicial: {type(first_exc).__name__}: {first_exc}\nInstalación/import CPU: {type(second_exc).__name__}: {second_exc}"

    with st.spinner("Preparando runtime SKEL CPU aislado (sin ModernGL)…"):
        torch, SKEL, runtime_error = _import_or_install_skel_cpu()
    runtime = torch is not None and SKEL is not None
    if not runtime:
        st.error("El bundle privado es válido, pero el runtime SKEL CPU no ha podido prepararse. V110.2.4 evita deliberadamente moderngl-window para mantener NumPy 2.x compatible con Pose2Sim/OpenSim.")
        st.code(runtime_error or "Error de importación no especificado")
    else:
        st.success(f"Runtime SKEL REAL detectado · PyTorch {torch.__version__} · modelo privado presente · modo CPU sin ModernGL.")

        # Extraer exclusivamente el PKL elegido a un directorio temporal escribible.
        genders=[]
        if audit.get("has_male"): genders.append("male")
        if audit.get("has_female"): genders.append("female")
        gender=st.selectbox("Modelo SKEL para la prueba de 1 frame",genders,index=0,key="v110_1_7_gender")
        model_name=f"skel_{gender}.pkl"
        model_root=Path(tempfile.gettempdir()) / "physiosentinel_skel_models_v110_1_7"
        model_root.mkdir(parents=True,exist_ok=True)
        model_path=model_root / model_name
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                matches=[n for n in z.namelist() if n.lower().endswith(model_name)]
                if not matches:
                    raise FileNotFoundError(model_name)
                with z.open(matches[0]) as src, open(model_path,"wb") as dst:
                    dst.write(src.read())
        except Exception as exc:
            st.error(f"No se pudo extraer {model_name} al runtime temporal: {type(exc).__name__}: {exc}")
            return

        def _build_skel_model():
            # El commit fijado y versiones posteriores han usado ambas convenciones:
            # model_path explícito o SKEL_MODEL_PATH/directorio por defecto. Probamos
            # de forma controlada sin escribir fuera de /tmp.
            errs=[]
            try:
                # En el commit c32cf165..., `model_path` debe ser el DIRECTORIO;
                # SKEL concatena internamente skel_<gender>.pkl.
                return SKEL(gender=gender, model_path=str(model_root)), "model_path=/tmp/.../", None
            except Exception as exc:
                errs.append(f"model_path=dir: {type(exc).__name__}: {exc}")
                return None, None, "\n".join(errs)

        with st.spinner("Instanciando SKEL y ejecutando el primer forward CPU (1 frame)…"):
            model, init_mode, init_error = _build_skel_model()
            if model is None:
                st.error("SKEL se importa correctamente, pero no ha podido abrir el modelo privado desde /tmp.")
                st.code(init_error or "Error de inicialización no especificado")
                return
            try:
                model=model.to("cpu")
                pose=torch.zeros((1,int(model.num_q_params)),dtype=torch.float32,device="cpu")
                betas=torch.zeros((1,int(model.num_betas)),dtype=torch.float32,device="cpu")
                trans=torch.zeros((1,3),dtype=torch.float32,device="cpu")
                with torch.no_grad():
                    out=model(pose,betas,trans)
                skin=getattr(out,"skin_verts",None)
                skelv=getattr(out,"skel_verts",None)
                joints=getattr(out,"joints",None)
                if joints is None:
                    joints=getattr(out,"joints_ori",None)
                st.success("✅ Primer forward SKEL REAL completado en CPU para 1 frame.")
                f1,f2,f3,f4=st.columns(4)
                f1.metric("q / pose",int(model.num_q_params))
                f2.metric("betas",int(model.num_betas))
                f3.metric("skin verts",int(skin.shape[-2]) if skin is not None else "—")
                f4.metric("skel verts",int(skelv.shape[-2]) if skelv is not None else "—")
                st.caption(f"Inicialización: {init_mode} · modelo privado: {model_name} · almacenamiento temporal: /tmp · batch=1 · CPU")
                if joints is not None:
                    st.caption(f"Salida articular SKEL: shape {tuple(joints.shape)}")
                st.info("Puerta de runtime superada. V110.2.4 calibra empíricamente q0…q45 y conserva después el retargeting jerárquico como secuencia de comparación.")

                st.markdown("### V110.2.4 · Calibración empírica de DOF SKEL")
                st.caption("Barrido diagnóstico q0…q45 alrededor de la pose neutra. No asigna etiquetas biomecánicas por intuición: mide qué joints mueve realmente cada parámetro, el eje global dominante y su signo. No modifica la marcha ni las métricas clínicas.")
                delta=st.select_slider("Perturbación de calibración (rad)",options=[0.05,0.08,0.12,0.18,0.25],value=0.12,key="v110_2_4_cal_delta")
                if st.button("🧭 Calibrar q0…q45 del modelo SKEL",type="primary",use_container_width=True,key="v110_2_4_calibrate_dof"):
                    cb=st.progress(0,text="Calibrando DOF SKEL…")
                    def _dcb(done,total,mx): cb.progress(min(1.0,float(done)/max(1,total)),text=f"q{done-1:02d}/{total-1:02d} · sensibilidad {mx:.4g}")
                    try:
                        dof_df,_=_calibrate_skel_dofs(torch,model,float(delta),_dcb)
                        st.session_state['v110_2_4_dof_df']=dof_df; st.session_state['v110_2_4_dof_delta']=float(delta)
                        cb.progress(1.0,text="Calibración DOF completada")
                    except Exception as dexc:
                        st.session_state.pop('v110_2_4_dof_df',None); st.error(f"Calibración DOF no completada: {type(dexc).__name__}: {dexc}")
                dof_df=st.session_state.get('v110_2_4_dof_df')
                if isinstance(dof_df,pd.DataFrame) and not dof_df.empty:
                    detectable=int(dof_df['efecto_detectable'].sum()); cdo1,cdo2,cdo3=st.columns(3)
                    cdo1.metric('q evaluados',len(dof_df)); cdo2.metric('q con efecto articular',detectable); cdo3.metric('q sin efecto detectable',len(dof_df)-detectable)
                    st.dataframe(dof_df,use_container_width=True,hide_index=True,height=440)
                    dnow=float(st.session_state.get('v110_2_4_dof_delta',delta)); cc1,cc2=st.columns(2)
                    with cc1: st.download_button('⬇️ Calibración DOF V110.2.4 (CSV)',dof_df.to_csv(index=False).encode('utf-8-sig'),'V110_2_4_SKEL_DOF_calibration.csv','text/csv',use_container_width=True)
                    with cc2: st.download_button('⬇️ Calibración DOF V110.2.4 (JSON)',_dof_calibration_json_bytes(dof_df,dnow,model),'V110_2_4_SKEL_DOF_calibration.json','application/json',use_container_width=True)
                    st.warning('Esta tabla es la referencia para la siguiente corrección de retargeting. Los nombres biomecánicos históricos de q no se consideran validados hasta contrastarlos con este barrido.')

                st.markdown("### V110.2.4 · Frame semilla SKEL ↔ XYZ")
                st.caption("Se optimiza la pose SKEL sobre sus joints anatómicos y se estima una transformación global rígida + escala isotrópica para registrar el sistema de coordenadas V104/V107. Betas permanecen neutras en esta puerta de validación.")
                try:
                    with st.spinner("Ajustando pose SKEL al frame XYZ (CPU, una sola vez)…"):
                        fit=_fit_one_skel_frame(torch,model,df,max_iter=120)
                    nfit=len(fit["rows"])
                    a1,a2,a3,a4=st.columns(4)
                    a1.metric("Correspondencias",f"{nfit}")
                    a2.metric("RMSE antes",f"{fit['rmse_before']:.4f}")
                    a3.metric("RMSE después",f"{fit['rmse_after']:.4f}")
                    improve=(1.0-fit['rmse_after']/max(fit['rmse_before'],1e-12))*100.0
                    a4.metric("Mejora",f"{improve:.1f} %")
                    if np.isfinite(improve) and improve>20:
                        st.success("✅ Ajuste del frame 1 completado: SKEL responde a la pose objetivo y reduce el error articular.")
                    else:
                        st.warning("El forward es válido, pero el primer ajuste todavía no reduce suficientemente el error. No se extenderá a 75 frames hasta revisar correspondencias/orientación.")
                    _plot_skel_fit(df,fit["rows"],fit["before"],fit["after"],fit.get("all_after"),fit.get("joint_names"))
                    erows=[]
                    for i,(target_name,jidx,skel_name) in enumerate(fit["rows"]):
                        erows.append({"XYZ objetivo":target_name,"SKEL joint":skel_name,"índice SKEL":jidx,"error antes":float(fit['errors_before'][i]),"error después":float(fit['errors_after'][i])})
                    with st.expander("Auditoría de correspondencias y error articular",expanded=False):
                        st.dataframe(pd.DataFrame(erows),use_container_width=True,hide_index=True)
                        st.write({"escala_global":fit["scale"],"traslacion_global":fit["trans"].tolist(),"rotacion_axis_angle":fit["rotvec"].tolist()})
                    export={
                        "version":"110.2.4","frame":int(best_i)+1,"gender":gender,"rmse_before":fit["rmse_before"],"rmse_after":fit["rmse_after"],
                        "scale":fit["scale"],"translation":fit["trans"].tolist(),"global_rotation_axis_angle":fit["rotvec"].tolist(),
                        "pose_46":fit["pose"].tolist(),
                        "correspondences":[{"target":r[0],"skel_index":int(r[1]),"skel_joint":r[2]} for r in fit["rows"]]
                    }
                    st.download_button("⬇️ Descargar ajuste SKEL frame 1 (JSON)",json.dumps(export,ensure_ascii=False,indent=2).encode("utf-8"),"V110_2_4_SKEL_fit_frame1.json","application/json",use_container_width=True)

                    st.markdown("### V110.2.4 · Propagación temporal 1→75")
                    st.caption("La escala corporal y betas quedan congeladas. V110.2.4 añade regularización anatómica en joints no observados, límites suaves de pose y continuidad temporal para impedir soluciones de bajo RMSE pero geométricamente deformadas.")
                    if st.button("▶️ Procesar secuencia completa y generar marcha SKEL",type="primary",use_container_width=True,key="v110_2_4_run_sequence"):
                        bar=st.progress(0,text="Preparando propagación temporal SKEL…")
                        status=st.empty()
                        def _pcb(done,total,rmse):
                            frac=min(1.0,max(0.0,float(done)/max(1,total)))
                            txt=f"Frame {done}/{total}" + (f" · RMSE {rmse:.4f}" if rmse is not None else "")
                            bar.progress(frac,text=txt); status.caption(txt)
                        try:
                            st.session_state.pop("v110_2_4_mesh_sequence",None)
                            seq=_fit_skel_sequence(torch,model,motion,fit,start_index=int(best_i),iterations=24,progress_cb=_pcb)
                            st.session_state["v110_2_4_sequence"]=seq
                            bar.progress(1.0,text="Secuencia SKEL completada")
                            status.empty()
                        except Exception as seq_exc:
                            st.session_state.pop("v110_2_4_sequence",None)
                            st.error("No se pudo completar la propagación temporal SKEL.")
                            st.code(f"{type(seq_exc).__name__}: {seq_exc}")
                    seq=st.session_state.get("v110_2_4_sequence")
                    if isinstance(seq,dict) and seq.get("frames"):
                        oks=[x for x in seq["frames"] if x.get("status")=="ok"]
                        rmses=np.array([x.get("rmse",np.nan) for x in oks],float) if oks else np.array([],float)
                        m1,m2,m3,m4=st.columns(4)
                        m1.metric("Frames resueltos",f"{len(oks)}/{len(frames)-int(best_i)}")
                        m2.metric("RMSE medio",f"{np.nanmean(rmses):.4f}" if rmses.size else "—")
                        m3.metric("RMSE máximo",f"{np.nanmax(rmses):.4f}" if rmses.size else "—")
                        m4.metric("Escala fija",f"{seq.get('scale',float('nan')):.4f}")
                        audits=[x.get("anatomical_audit",{}) for x in oks]
                        unsafe=[a for a in audits if not a.get("ok",True)]
                        if unsafe:
                            st.warning(f"Control anatómico: {len(unsafe)} frame(s) mantienen alguna alerta geométrica. Revísalos antes de generar la malla.")
                        else:
                            st.success("✅ Control anatómico superado en todos los frames resueltos: sin plegados extremos detectados por la auditoría V110.2.4.")
                        if len(oks)>=max(2,int(0.9*(len(frames)-int(best_i)))):
                            st.success("✅ Propagación temporal completada. SKEL dispone ya de una pose continua para la secuencia V104/V107 y puede reproducirse como marcha articulada.")
                        else:
                            st.warning("La secuencia se ha generado parcialmente. Revisa los frames con landmarks insuficientes antes de considerarla validada.")
                        st.markdown('### Referencia cinemática · vídeo 3D simplificado no calibrado')
                        st.caption('Referencia V104/V107 recuperada para comparar la cinemática objetivo con SKEL. No representa 3D métrico calibrado.')
                        _plot_simplified_xyz_animation(motion)
                        _plot_skel_sequence_animation(seq)
                        export_seq={k:v for k,v in seq.items()}
                        st.download_button("⬇️ Descargar secuencia SKEL V110.2.4 (JSON)",json.dumps(export_seq,ensure_ascii=False).encode("utf-8"),"V110_2_4_SKEL_sequence.json","application/json",use_container_width=True)
                        with st.expander("Auditoría temporal por frame",expanded=False):
                            audit_rows=[{"frame":x.get("frame"),"estado":x.get("status"),"correspondencias":x.get("n_correspondences"),"RMSE":x.get("rmse"),"anatómico":"OK" if x.get("anatomical_audit",{}).get("ok",True) else "REVISAR","alertas":"; ".join(x.get("anatomical_audit",{}).get("flags",[]))} for x in seq["frames"]]
                            st.dataframe(pd.DataFrame(audit_rows),use_container_width=True,hide_index=True)

                        st.markdown("### V110.2.4 · SKEL MESH WALKER")
                        st.caption("Convierte exclusivamente la secuencia V110.2.4 activa en `skin_verts`: no reutiliza estados de V110.1.9/V110.2.1. Betas=0 y la escala se copia y verifica contra la secuencia temporal actual antes de guardar el NPZ.")
                        if st.button("🧍▶️ Generar malla corporal SKEL y reproducir marcha",type="primary",use_container_width=True,key="v110_2_4_build_skin_mesh"):
                            mb=st.progress(0,text="Preparando malla corporal SKEL…")
                            ms=st.empty()
                            def _mpcb(done,total,nverts):
                                frac=min(1.0,max(0.0,float(done)/max(1,total)))
                                txt=f"Malla frame {done}/{total} · {nverts} vértices"
                                mb.progress(frac,text=txt); ms.caption(txt)
                            try:
                                unsafe_frames=[x for x in seq.get("frames",[]) if x.get("status")=="ok" and not x.get("anatomical_audit",{}).get("ok",True)]
                                if unsafe_frames:
                                    st.warning(f"Se generará la malla con {len(unsafe_frames)} alerta(s) anatómica(s) para inspección; la versión las conserva en la auditoría.")
                                mesh_seq=_build_skel_skin_sequence(torch,model,seq,progress_cb=_mpcb)
                                if abs(float(mesh_seq.get("scale",0))-float(seq.get("scale",0)))>1e-7:
                                    raise RuntimeError("La escala de la malla no coincide con la secuencia temporal activa.")
                                st.session_state["v110_2_4_mesh_sequence"]=mesh_seq
                                mb.progress(1.0,text="Malla SKEL 75 frames completada")
                                ms.empty()
                            except Exception as mesh_exc:
                                st.session_state.pop("v110_2_4_mesh_sequence",None)
                                st.error("La marcha articular está validada, pero no se pudo generar la malla corporal SKEL.")
                                st.code(f"{type(mesh_exc).__name__}: {mesh_exc}")
                        mesh_seq=st.session_state.get("v110_2_4_mesh_sequence")
                        if isinstance(mesh_seq,dict) and isinstance(mesh_seq.get("vertices"),np.ndarray):
                            VV=mesh_seq["vertices"]; FF=mesh_seq["faces"]
                            z1,z2,z3,z4=st.columns(4)
                            z1.metric("Frames malla",int(VV.shape[0]))
                            z2.metric("Vértices/frame",int(VV.shape[1]))
                            z3.metric("Triángulos",int(FF.shape[0]))
                            z4.metric("Topología",str(mesh_seq.get("face_source","skin_f")))
                            if VV.shape[0]==len(oks):
                                st.success("✅ SKEL MESH WALKER generado. La misma malla corporal se ha deformado sobre toda la secuencia temporal validada.")
                            _plot_skel_mesh_walker(mesh_seq)
                            st.download_button("⬇️ Descargar SKEL Mesh Walker V110.2.4 (NPZ)",_mesh_sequence_npz_bytes(mesh_seq),"V110_2_4_SKEL_mesh_sequence.npz","application/octet-stream",use_container_width=True)
                            st.caption("NPZ científico compacto: vertices[frame,6890,3], faces[triángulo,3], joints, frame_ids, escala y betas. No incluye ni redistribuye el PKL privado SKEL.")
                            st.markdown('### V110.2.4 · Validación sincronizada Side-by-Side')
                            st.caption('El mismo frame se representa simultáneamente como XYZ simplificado V104/V107, joints SKEL y malla SKEL. El objetivo es localizar ejes/signos incorrectos sin dejar que el RMSE oculte una postura anatómicamente errónea.')
                            _side_by_side_validation(motion,seq,mesh_seq)
                        else:
                            st.info("La secuencia articular ya está lista. Pulsa el botón de MESH WALKER para convertir esas 75 poses en el modelo corporal SKEL animado.")
                    else:
                        st.info("El frame semilla está validado. Pulsa el botón anterior para resolver frames 2→75; después V110.2.4 habilitará la malla corporal animada.")
                except Exception as fit_exc:
                    st.error("SKEL funciona, pero V110.2.4 no ha podido completar el ajuste del frame semilla.")
                    st.code(f"{type(fit_exc).__name__}: {fit_exc}")
            except Exception as exc:
                st.error("El modelo SKEL se ha instanciado, pero el primer forward CPU ha fallado.")
                st.code(f"{type(exc).__name__}: {exc}")
                return
