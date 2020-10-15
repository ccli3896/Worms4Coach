import gym
from gym import spaces
from improc import *
import numpy as np
import matplotlib.pyplot as plt
import time

def add_to_traj(trajectory,info):
    # appends each key in info to the corresponding key in trajectory.
    # If trajectory is empty, returns trajectory as copy of info but with each element as list
    # so it can be appended to in the future.

    if trajectory:
        for k in info.keys():
            trajectory[k].append(info[k])
    else:
        for k in info.keys():
            trajectory[k] = [info[k]]

class ProcessedWorm(gym.Env):
    """Custom Environment that follows gym interface"""
    metadata = {'render.modes': ['human']}

    def __init__(self, target, ep_len=500, ht_time=3):
        
        """
        Initializes the camera, light, worm starting point.
        ep_len is in seconds; each episode will terminate afterward. 
        """
        super(ProcessedWorm, self).__init__()
        # For clarity: last_loc is for calculating reward. old_loc is for HT checks.

        # Define action and observation space
        # They must be gym.spaces objects

        self.action_space = spaces.Box(low=0,high=1,shape=(1,),dtype=np.float32)
        self.observation_space = spaces.Box(low=np.array([-180,-180]), high=np.array([180,180]), dtype=np.uint8)

        self.target = target
        self.ep_len = ep_len
        self.templates, self.bodies = load_templates()
        self.cam, self.task = init_instruments()
        #self.bg = self.make_bgs()[0]

        self.timer = Timer(ep_len)
        self.ht_timer= Timer(ht_time)
        self.steps = 0
        self.finished = False


    def step(self, action, sleep_time=0):
        """Chooses action and returns a (step_type, reward, discount, observation)"""
        # In info, returns worm info for that step 
        # {'img':_, 'loc':(x,y), 't':_}

        self.steps += 1

        self.task.write(action)
        time.sleep(sleep_time)

        # Get data
        img = grab_im(self.cam, self.bg)
        worms = find_worms(img, self.templates, self.bodies, ref_pts=[self.head], num_worms=1)

        # Timer checks: episode end and HT
        if self.steps > self.ep_len:
            self.finished = True
        self.timer.update()
        self.ht_timer.update()
        if self.ht_timer.check():
            SWITCHED = self.check_ht()

        if worms is None:
            # Returns zeros if worm isn't found or something went wrong.
            self.task.write(0)
            print(f'No worm \t\t\r',end='')
            return np.zeros(2), 0, self.finished, {
                #'img': None,
                'loc': np.zeros(2),
                't': self.timer.t,
                'endpts': np.zeros((2,2))-1,
                'obs': np.zeros(2),
                'reward': 0,
                'target': self.target,
                'action': action
                }
        
        # Find state 
        self.worm = worms[0]
        body_dir = relative_angle(self.worm['body'], self.target)
        head_body = relative_angle(self.worm['angs'][0], self.worm['body'])
        obs = np.array([body_dir, head_body])
        
        # Find reward and then update last_loc variable
        reward = proj(self.worm['loc']-self.last_loc, [np.cos(self.target*pi/180),-np.sin(self.target*pi/180)])
        self.last_loc = self.worm['loc']
        if np.isnan(reward) or np.abs(reward)>10:
            reward = 0
        
        # return obs, reward, done (boolean), info (dict)
        return obs, reward, self.finished, {
            #'img': self.worm['img'],
            'loc': self.worm['loc'],
            't': self.timer.t,
            'endpts': self.worm['endpts'],
            'obs': obs,
            'reward': reward,
            'target': self.target,
            'action': action
        }

        
    def reset(self,target=None):
        """Returns the first `TimeStep` of a new episode."""
        if target is not None:
            self.target = target
        else:
            # Rotates target by 90 deg on each reset
            self.target = (self.target+90)%360
        self.head, self.old_loc = [0,0],[1,1]
        self.last_loc = self.old_loc

        self.bg = self.make_bgs()[0]

        self.timer.reset()
        self.ht_timer.reset()
        self.finished = False
        self.steps = 0
        
        # Takes one step and returns the observation
        return self.step(0)[0]
    
    def render(self, mode='human', close=False):
        # Render the environment to the screen
        # img = grab_im(self.cam, self.bg)
        # worms = find_worms(img, self.templates, self.bodies, ref_pts=[self.head], num_worms=1)
        # if worms is None:
        #     # Returns nans if no worm is found or something went wrong
        #     self.task.write(0)
        #     self.bg = self.bg
        #     print('No worm')
        #     return
        # worm = worms[0]
        # print(worm)
        # plt.imshow(worm['img'])
        pass

    """ BELOW: UTILITY FUNCTIONS """
    def make_bgs(self, light_vec=[0], total_time=20):
        """Makes background images and stores in self"""
        return make_vec_bg(self.cam,self.task,light_vec,total_time=total_time)
        
    def test_cam(self,bg=None):
        """To check camera is working, with or without background subtraction"""
        return grab_im(self.cam, bg)
    
    def check_ht(self):
        """
        Run this function every few seconds to make sure HT orientation is correct
        Returns True if switched.
        """
        self.head, SWITCH = ht_quick(self.worm, self.old_loc)
        self.old_loc = self.worm['loc']
        return SWITCH

    def close(self):
        self.cam.exit()
        self.task.write(0)