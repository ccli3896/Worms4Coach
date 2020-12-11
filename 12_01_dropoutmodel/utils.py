import pickle
import matplotlib.pyplot as plt 
import numpy as np
import pandas as pd 

# Interaction should be mainly with these functions

def make_df(fnames, 
    old_frame=None, 
    reward_ahead=10, 
    timestep_gap=1, 
    prev_act_window=3, 
    jump_limit=100,
    ):

    '''
    Takes a file and turns it into a trajectory dataframe.
    Can add to old data.
    Inputs:
                old_frame: old df
             reward_ahead: how many steps ahead to sum reward, for each table entry
             timestep_gap: how data are sampled (e.g. =5 means only every fifth datapoint is kept)
          prev_act_window: how many steps to look back to make sure all actions were 'on' or 'off'
               jump_limit: data are processed to remove faulty points where worm loc has jumped really far.
                           This is the maximum jump distance allowed before points are tossed.

    Output:
        dataframe object with keys:
            't', 'obs_b', 'obs_h', 'prev_actions', 'next_obs_b', 'next_obs_h', 'reward', 'loc'
    '''
    def add_ind_to_df(traj,df,i, reward_ahead, prev_act_window):
        return df.append({
            't'           : traj['t'][i],
            'obs_b'       : traj['obs'][i][0],
            'obs_h'       : traj['obs'][i][1],
            'prev_actions': sum(traj['action'][i-prev_act_window+1:i+1]), # Includes current action
            'next_obs_b'  : traj['obs'][i+1][0],
            'next_obs_h'  : traj['obs'][i+1][1],
            'reward'      : sum(traj['reward'][i:i+reward_ahead]),
            'loc'         : traj['loc'][i],
        }, ignore_index=True)

    if old_frame is None:
        df = pd.DataFrame(columns = ['t', 
            'obs_b', 'obs_h', 'prev_actions', 
            'next_obs_b', 'next_obs_h', 'reward', 'loc'])
    else:
        df = old_frame

    # For every file, loop through and remove problem points.
    for fname in fnames:
        newf = True
        with open(fname, 'rb') as f:
            traj = pickle.load(f)

        for i in np.arange(prev_act_window+1,len(traj['t'])-reward_ahead,timestep_gap):
            # For every timestep, check if the jump is reasonable and add to dataframe.
            # Reset for new files
            if newf:
                if sum(traj['loc'][i])!=0:
                    df = add_ind_to_df(traj,df,i,reward_ahead,prev_act_window)
                    newf = False
            elif np.sqrt(np.sum(np.square(df['loc'].iloc[-1]-traj['loc'][i]))) < jump_limit:
                df = add_ind_to_df(traj,df,i,reward_ahead,prev_act_window)

    return df

def make_dist_dict(df, sm_pars=None,
    prev_act_window=3):
    # Makes a dictionary of distributions using trajectory statistics.
    # sm_pars is a dict of form {'lambda': .05, 'iters': 30}
    #     If None, then no smoothing.

    traj_on = df.query('prev_actions=='+str(prev_act_window))
    traj_off = df.query('prev_actions==0')

    pass
#############################################3
# NEEDS TO BE FINISHED


def make_stat_mats(df):
    # This version, compared to old utils DOES NOT remove HT-switches.
    # Inner func does most of the work querying for each obs.
    # Returns everything at once: 
    #   r_mat[12,12,2], b_mat[12,12,2], h_mat[12,12,2], counts[12,12].

    def get_stats_angs(df,obs):
        # Gets mean and var of df values that match obs, centered on obs
        series = df.query('obs_b=='+str(obs[0])+'& obs_h=='+str(obs[1]))
        series['']
### STOPPED RIGHT HERE
###################################################3

    r_mat = np.zeros((12,12,2)) + np.nan 
    b_mat = np.zeros((12,12,2)) + np.nan 
    h_mat = np.zeros((12,12,2)) + np.nan 
    counts = np.zeros((12,12))

    for i,theta_b in enumerate(np.arange(-180,180,30)):
        for j,theta_h in enumerate(np.arange(-180,180,30)):
            r_sts,b_sts,h_sts,counts[i,j] = get_stats_angs(df,[theta_b,theta_h])
            r_mat[i,j,:] = r_sts
            b_mat[i,j,:] = b_sts
            h_mat[i,j,:] = h_sts

    return r_mat, b_mat, h_mat, counts

'''
Matrix regularizers: interpolation and smoothing
'''
def lin_interp_mat(mat,ang,wraparound=True):
    # Fills in NaNs in matrix by linear interpolation. 
    # Only considers nearest neighbors (no diagonals).
    # Fills in NaNs from most neighbors to least neighbors.
    # wraparound extends matrix in all four directions. 
    if ang:
        buffer=180
    else:
        buffer=1e5

    mat = make_wraparound(mat,ang,wraparound=wraparound)

    # Find nans in relevant matrix section
    nan_inds = np.argwhere(np.isnan(mat[1:-1,1:-1])) + 1
        # add 1 because need index for extended matrix
    
    neighbor_lim = 3
    while nan_inds.size>0:
        candidates = 0
        for ind in nan_inds:
            neighbors = get_neighbors(mat,ind)
            if sum(~np.isnan(neighbors)) >= neighbor_lim:
                mat[ind[0],ind[1]] = np.mean(wrap_correct(neighbors[~np.isnan(neighbors)], ref=min(neighbors), buffer=buffer))
                candidates+=1
        if candidates==0:
            neighbor_lim-=1
        nan_inds = np.argwhere(np.isnan(mat[1:-1,1:-1])) + 1

    return set_range(mat[1:-1,1:-1])

def smoothen(matrix,counts,ang,smooth_par=.05,iters=30,wraparound=True,diagonals=True): 
    # matrix is in form [12,12]
    # counts is [12,12].
    # ang is bool, True if angle matrix
    # Will start with a simple linear weighting/smoothing. 
    
    # So the shapes start out right before looping 
    matrix = make_wraparound(matrix, ang, wraparound=True)
    counts = make_wraparound(counts, False, wraparound=True)
    
    for it in range(iters):
        matrix = make_wraparound(matrix[1:-1,1:-1], ang, wraparound=True)
        tempmat = np.copy(matrix) # Now tempmat and matrix are the same extended size
        rows,cols = np.array(matrix.shape)-2 

        # Loops through each matrix element and weights changes by counts
        for i in np.arange(rows)+1:
            for j in np.arange(cols)+1:
                neighs = np.append(get_neighbors(matrix,(i,j)), matrix[i,j])
                neigh_counts = np.append(get_neighbors(counts,(i,j)), counts[i,j])
                del_sm = np.sum(np.multiply(neigh_counts, neighs))
                if diagonals:
                    # Diagonal entries (scaled by 1/sqrt(2))
                    neighs_d = np.append(get_diags(matrix,(i,j)), matrix[i,j])
                    neighs_counts_d = np.append(get_diags(counts,(i,j)), counts[i,j])
                    del_sm_d = (np.sum(np.multiply(neighs_counts_d, neighs_d)))/np.sqrt(2)
                    Z = np.sum(neigh_counts) + np.sum(neighs_counts_d)/np.sqrt(2)
                else:
                    del_sm_d = 0
                    Z = np.sum(neigh_counts)

                tempmat[i,j] = tempmat[i,j] + smooth_par*(del_sm/Z+del_sm_d/Z - tempmat[i,j])
                
        # After tempmat is updated, set reference matrix to be the same
        # This way updates within one iteration don't get included in the same iteration
        matrix = np.copy(tempmat)
    
    return matrix[1:-1,1:-1]


'''
Small funcs and utils
'''
def wrap_correct(arr,ref=0,buffer=180):
    # Takes angles and translates them to +/-buffer around ref.
    # For things like std, use large buffer so it doesn't change
    # If both arrays, send each element through this function.
    if hasattr(arr,"__len__"):
        if hasattr(ref,"__len__"):
            for i in range(len(arr)):
                arr[i] = wrap_correct(arr[i],ref=ref[i])
        # If only arr is an array
        else:
            arr[arr<ref-buffer]+=buffer*2
            arr[arr>=ref+buffer]-=buffer*2
            if len(arr[arr<ref-buffer])>0 or len(arr[arr>=ref+buffer])>0:
                arr = wrap_correct(arr,ref=ref)
    else:
        if arr<ref-buffer:
            arr+=buffer*2
            if arr<ref-buffer:
                arr = wrap_correct(arr,ref=ref)
        elif arr>=ref+buffer:
            arr-=buffer*2
            if arr>=ref+buffer:
                arr = wrap_correct(arr,ref=ref)
    return arr
        
def make_wraparound(mat,ang,wraparound=True):
    # Expands matrix for wraparound interpolation
    # If matrix is angle values, set ang=True.
    mat_new = np.zeros((np.array(mat.shape)+2)) + np.nan
    mat_new[1:-1,1:-1] = mat
    if ang:
        buffer=180
    else:
        buffer=1e5

    if wraparound:
        # diagonals
        mat_new[0,0] = wrap_correct(mat[-1,-1], ref=mat[0,0], buffer=buffer)
        mat_new[0,-1] = wrap_correct(mat[-1,0], ref=mat[0,-1], buffer=buffer)
        mat_new[-1,0] = wrap_correct(mat[0,-1], ref=mat[-1,0], buffer=buffer)
        mat_new[-1,-1] = wrap_correct(mat[0,0], ref=mat[-1,-1], buffer=buffer)
        # adjacents
        mat_new[0,1:-1] = wrap_correct(mat[-1,:], ref=mat[0,:], buffer=buffer)
        mat_new[-1,1:-1] = wrap_correct(mat[0,:], ref=mat[-1,:], buffer=buffer)
        mat_new[1:-1,0] = wrap_correct(mat[:,-1], ref=mat[:,0], buffer=buffer)
        mat_new[1:-1,-1] = wrap_correct(mat[:,0], ref=mat[:,-1], buffer=buffer)
    return mat_new

def get_neighbors(mat,i):
    # Makes array of four neighbors around mat[index]
    # index is a pair
    return np.array([mat[i[0],i[1]-1], mat[i[0],i[1]+1], mat[i[0]-1,i[1]], mat[i[0]+1,i[1]]])

def get_diags(mat,i):
    return np.array([mat[i[0]-1,i[1]-1], mat[i[0]-1,i[1]+1], mat[i[0]+1,i[1]-1], mat[i[0]+1,i[1]+1]])

