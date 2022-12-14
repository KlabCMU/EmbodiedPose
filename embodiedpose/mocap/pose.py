import numpy as np
import math
from mocap.bvh import Bvh
from embodiedpose.utils.transformation import quaternion_slerp, quaternion_from_euler, euler_from_quaternion
import os


def load_amc_file(fname, scale):

    with open(fname) as f:
        content = f.readlines()

    bone_addr = dict()
    poses = []
    cur_pos = None
    fr = 1
    for line in content:
        line_words = line.split()
        cmd = line_words[0]
        if cmd == str(fr):
            if cur_pos:
                poses.append(np.array(cur_pos))
            cur_pos = []
            fr += 1
        elif cur_pos is not None:
            start_ind = len(cur_pos)
            if cmd == 'root':
                cur_pos += [float(word) * scale for word in line_words[1:4]]
                cur_pos += [
                    math.radians(float(word)) for word in line_words[4:]
                ]
            elif cmd == 'lfoot' or cmd == 'rfoot':
                cur_pos += reversed(
                    [math.radians(float(word)) for word in line_words[1:]])
                if len(cur_pos) < 3:
                    cur_pos.insert(-1, 0.0)
            else:
                cur_pos += reversed(
                    [math.radians(float(word)) for word in line_words[1:]])
            if fr == 2:
                end_ind = len(cur_pos)
                bone_addr[cmd] = (start_ind, end_ind)

    if cur_pos:
        poses.append(np.array(cur_pos))
    poses = np.vstack(poses)
    return poses, bone_addr


def load_bvh_file(fname, skeleton):
    with open(fname) as f:
        mocap = Bvh(f.read())

    # build bone_addr
    bone_addr = dict()
    start_ind = 0
    for bone in skeleton.bones:
        end_ind = start_ind + len(bone.channels)
        bone_addr[bone.name] = (start_ind, end_ind)
        start_ind = end_ind
    dof_num = start_ind

    poses = np.zeros((mocap.nframes, dof_num))
    for i in range(mocap.nframes):
        for bone in skeleton.bones:
            trans = np.array(
                mocap.frame_joint_channels(i, bone.name, bone.channels))
            if bone == skeleton.root:
                trans[:3] *= skeleton.len_scale
                trans[3:6] = np.deg2rad(trans[3:6])
            else:
                trans = np.deg2rad(trans)
            start_ind, end_ind = bone_addr[bone.name]
            poses[i, start_ind:end_ind] = trans

    return poses, bone_addr, mocap.frame_rate


##numpy genfromtxt parser
def load_obj_bvh_file(fname):
    len_scale = 0.0254
    skip_line = 9
    #skip_line = 54
    data = np.genfromtxt(fname,
                         dtype=float,
                         delimiter=' ',
                         skip_header=skip_line)[:, :6]
    data[:, :3] *= len_scale
    data[:, 3:] = np.deg2rad(data[:, 3:])

    f = open(fname)
    frameRate = float(f.readlines()[skip_line - 1].split(':')[1].rstrip(
        os.linesep))

    return data, round(1.0 / frameRate)


def load_obj_position(fname):
    len_scale = 0.0254
    data = np.genfromtxt(fname, dtype=float, delimiter=' ',
                         skip_header=9)[:, :3]
    data[:, :] *= len_scale
    return np.mean(data, axis=0)


def lin_interp(pose1, pose2, t):
    pose_t = (1 - t) * pose1 + t * pose2
    return pose_t


def interpolated_traj(poses, sample_t=0.030, mocap_fr=120):
    N = poses.shape[0]
    T = float(N - 1) / mocap_fr
    num = int(math.floor(T / sample_t))
    sampling_times = np.arange(num + 1) * sample_t * mocap_fr

    poses_samp = []
    for t in sampling_times:
        start = int(math.floor(t))
        end = min(int(math.ceil(t)), poses.shape[0] - 1)
        poses_samp.append(
            lin_interp(poses[start, :], poses[end, :], t - math.floor(t)))
    poses_samp = np.vstack(poses_samp)

    return poses_samp
