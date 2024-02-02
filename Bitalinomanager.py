import time
import numpy as np
from bitalino import BITalino # Official Bitalino repository
from bitalino import ExceptionCode as BITalinoExceptionCode
import os
import datetime as dt
import matplotlib.pyplot as plt
import pandas as pd
import sys
# For mutiprocessing and interprocess communication
import subprocess
import shlex
import signal
import json

# PPE STRESS : Device MAC Address : 00:21:08:35:14:75
# PPE Fatigue : Device MAC Address : 00:21:08:35:16:A0
#   The macAddress variable on Windows can be "XX:XX:XX:XX:XX:XX" or "COMX"
#   while on Mac OS can be "/dev/tty.BITalino-XX-XX-DevB" for devices ending with the last 4 digits of the MAC address or "/dev/tty.BITalino-DevB" for the remaining


# Possible values of Acquisition Channels
_ACQ_CHANNELS = { 'A1':0,'A2':1,'A3':2,'A4':3,'A5':4,'A6':5 }
# Possible values of Sensor Types
_SENSOR_TYPES = ['EDA', 'ECG', 'RAW'] # You may add other sensors here (By default other sensor data is stored in RAW format)
                    
# A useful function to find key corresponding to a value in dict
def get_key(dictionary, value):
    return next((key for key, val in dictionary.items() if val == value), None)

# A useful extension of dict class
class DictWithAttributes(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'DictWithAttributes' object has no attribute '{key}'")
    def __setattr__(self, key, value):
        if key in self:
            self[key] = value
        else:
            raise KeyError(f"Key '{key}' does not exist in the dictionary")


# A class to simplify interaction with Bitalino device
# Added functionality : 
#       + Save sensor/raw data to csv file
#       + Show live plot
#
# Usage :
#       Bitalino_Manager.connect() => Connect to Bitalino device                 
#       Bitalino_Manager.start_aquisition() => Connect (if not already connected) -> Start receiving data -> Disconnect
#       Bitalino_Manager.disconnect() => Disconnect from the connected device
class Bitalino_Manager :

    '''
        Device Config / Parameters
    '''
    DEFAULT_DEVICE_STATE = { 
        "MAC" : "", # MAC Address
        "selected_channels" : [0], # channel selected for data aquisition (default A1) (should be one of : 'A1':0,'A2':1,'A3':2,'A4':3,'A5':4,'A6':5)
        "sampling_rate" : 100, # channel sampling rate (should be one of : 1, 10, 100, 1000)
        "connected" : False # should always be False
    }
    
    # device handle
    device:BITalino
    device_state = DictWithAttributes(DEFAULT_DEVICE_STATE)
    
    # Keep track of failed connections
    connection_failed_counter = 0
    
    # result
    collected_data = {} # {timestamp : {SENSOR_TYPE : [values]} }

    '''
        Transfer Functions
    '''
    # Convert raw data to EDA (in µS)
    def _raw_to_eda_uS(raw_data):
        VCC = 3.3
        eda_uS = raw_data * VCC 
        n = 10 # number of channel bits n = 10 for A1 to A4, whereas for A5 and A6 it may be n = 6.
        eda_uS = eda_uS / ( 0.132 * (2**n))
        return eda_uS
    
    
    # Convert raw data to ECG (in mV)
    # Caution : I did not had time to verify the output of this function. 
    def _raw_to_ecg_mv(raw_data):
        VCC = 3.3 # operating voltage
        G = 1100 # sensor gain
        n = 10 # number of channel bits n = 10 for A1 to A4, whereas for A5 and A6 it may be n = 6.
        ecg = raw_data/(2**n)
        ecg -= 0.5
        ecg *= (VCC/G) # Volts
        ecg_mv = ecg * 1000
        return ecg_mv

                      
    '''
        Functions for device configuration
    '''

    # Select channels for data aquisition
    # Accepted 'channels' values : A1, A2, A3, A4, A5, A6
    def _select_channels(channels:[]):
        
        Bitalino_Manager.device_state.selected_channels = []
        for c in channels:
            if c in _ACQ_CHANNELS.keys():
                Bitalino_Manager.device_state.selected_channels.append(_ACQ_CHANNELS[c])
            else : 
                raise Exception(f"[Invalid channel] : {c}. Select from accepted channel values : A1, A2, A3, A4, A5, A6")

    def _select_sampling_rate(rate):
        # Possible sampling rates : 1, 10, 100, 1000
        _SAMPLING_RATES = {1, 10, 100, 1000}
        if rate in _SAMPLING_RATES :
            Bitalino_Manager.device_state.sampling_rate = rate
        else :
            print(f"Invalid sampling rate : {rate}")
            print(f"Selecting default sampling rate : {Bitalino_Manager.DEFAULT_DEVICE_STATE.sampling_rate}")
            Bitalino_Manager.device_state.sampling_rate = Bitalino_Manager.DEFAULT_DEVICE_STATE.sampling_rate # default rate 100


    ''' 
        User Functions to interact with the device
    '''
    # Connect to the device
    # macAddress = None (connect to default MAC address)
    # returns connection status or raise exception with keyword [Connection Error]
    def connect(macAddress = None, timeout=5, print_state=False):
        try:
            if macAddress is None:
                macAddress = Bitalino_Manager.DEFAULT_DEVICE_STATE.MAC
            
            # Connect to BITalino
            print(f"Trying to reach {macAddress}")
            Bitalino_Manager.device = BITalino(macAddress, timeout)
            
            # Read BITalino version
            print(f"Connected to {macAddress} : {Bitalino_Manager.device.version()}")
            # Read device state
            if print_state :
                print("##############################")
                print("Device Initial State : ")
                for key, value in Bitalino_Manager.device.state().items():
                    print(key, ":", value)
                print("##############################")
                
            Bitalino_Manager.connection_failed_counter = 0
            Bitalino_Manager.device_state.MAC = macAddress
            Bitalino_Manager.device_state.connected = True
        except Exception as e:
            _msg = f"[Connection Error] : {e}"
            Bitalino_Manager.connection_failed_counter +=1
            Bitalino_Manager.device_state.connected = False
            print(_msg, flush=True)
            raise Exception(_msg)
        
        return Bitalino_Manager.device_state.connected # return connection status


    # Disconnect from the device
    def disconnect():
        # Disconnect from BITalino
        Bitalino_Manager.device.close()
        Bitalino_Manager.device_state.connected = False
        print(f"Disconnected !")

    # Start Data Acquisition
    # runtime : int = data aquisition time in seconds. default = 0 : indefinite run time
    # nSamples : int  = Number of samples to be fetched by read() function. (default = 100) [Caution : Avoid small nSamples values to prevent device overload !]
    # macAddress : str = device mac address to attemp connection if not already connected
    # channels : dict {'channel' : 'sensor_type'} = default {'A1' : 'EDA'}. 
    #            Accepted channels : A1, A2, A3, A4, A5, A6
    #            Accepted sensor_types : EDA, ECG, RAW
    def start_aquisition(runtime=0, channels={'A1' : 'EDA'}, samplingRate=100, nSamples=100, show_live_plot=False, macAddress = None, save_to_file=False, file_name_prefix = "BITALINO", print_sample_log = False):

        # If no device connected. Connect.
        if Bitalino_Manager.device_state.connected is False:
            print("No device connected! Attempting to connect...")
            Bitalino_Manager.connect(macAddress=macAddress) # Connect or raise exception with keyword [Connection Error]

        try:
            Bitalino_Manager._select_sampling_rate(samplingRate)
            Bitalino_Manager._select_channels(channels.keys()) # Select channel or raise error with keyword [Invalid channel]

            # Check sensor types
            for ch,sensor in channels.items():
                if sensor not in _SENSOR_TYPES : # if invalid sensor type
                    print(f"Invalid sensor type : {sensor}. Switching to RAW aquisition mode for channel {ch}")
                    channels[ch] = 'RAW'
            
            print(f"[Start Read Data] from channel(s) : {[get_key(_ACQ_CHANNELS,sc) for sc in Bitalino_Manager.device_state.selected_channels]}", flush=True)

            # Start Acquisition
            Bitalino_Manager.device.start(Bitalino_Manager.device_state.sampling_rate, Bitalino_Manager.device_state.selected_channels)

            start = time.time()
            sesssion_time_stamp = time.strftime("%d-%m-%Y-%H%M%S", time.localtime(start))
            collected_data_in_this_session = {}

            # Create figure for plotting
            if show_live_plot:
                print("Launch Plot Window ...")
                _plot_labels = ' '.join(map(str, channels.values()))
                commandline = f"python3 liveplot.py {Bitalino_Manager.device_state.sampling_rate} {_plot_labels}"
                args = shlex.split(commandline)
                print(args)
                p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


                    
            # Loop to fetch data from the device
            while True:
                # Read samples
                _read_data = Bitalino_Manager.device.read(nSamples) 
                # NOTE :
                # Channel Data is aquired in same order as given to _select_channels() function
                # With additional 1 column for sequence number and 4 columns for digital IO (always present)
                # i.e. for selected analog channels A1 and A3 
                # _read_data contains columns : [seqNum Digital_0 Digital_1 Digital_2 Digital_3 A1 A3]
                # => sensor data can be found using a column offset = 5
                COLUMN_OFFSET = 5

                # Convert Raw Data to corresponding sensor value
                for i, (ch, sensor) in enumerate(channels.items()):
                    if sensor == 'EDA':
                        # _sensor_data = Bitalino_Manager._raw_to_eda_uS(_read_data[:,5:5+len(Bitalino_Manager.selected_channels)].flatten())
                        _sensor_data = Bitalino_Manager._raw_to_eda_uS(_read_data[:,COLUMN_OFFSET+i].flatten())
                    if sensor == 'ECG':
                        _sensor_data = Bitalino_Manager._raw_to_ecg_mv(_read_data[:,COLUMN_OFFSET+i].flatten())                        
                    else: # 'RAW'                    
                        _sensor_data = _read_data[:,COLUMN_OFFSET+i].flatten()
                    
                    # Store data
                    if len(collected_data_in_this_session.get(sensor,[])) > 0:
                        collected_data_in_this_session[sensor] = np.append(collected_data_in_this_session[sensor], _sensor_data, axis=0)        
                    else : collected_data_in_this_session[sensor] = _sensor_data
                                                
                if print_sample_log : print(f"Collected samples {np.array(list(collected_data_in_this_session.values())).shape }", flush=True)
                sys.stderr.flush()
                
                if show_live_plot is True:
                    # Create figure for plotting
                    # Convert the NumPy array to a JSON string
                    _max_one_min_values = int(60*Bitalino_Manager.device_state.sampling_rate) # send only last 60 sec data
                    _tmp = np.array(list(collected_data_in_this_session.values()))[:,-_max_one_min_values:].tolist()
                    arr_json = json.dumps(_tmp)
                    p.stdin.write(arr_json + '\n')
                    p.stdin.flush()
                    # print(_idx,"send plot update")
                    # time.sleep(1)
                    
                if runtime > 0:
                    end = time.time()
                    if end-start >= runtime:
                        print("Interrupt on time out ", end-start, " sec.")
                        break    
                
            
        except KeyboardInterrupt:
                print("[KeyboardInterrupt] Interrupt by Ctrl+C")

        except Exception as e:
            if str(e) == str(BITalinoExceptionCode.CONTACTING_DEVICE):
                print("[Connection lost] Error : ", e.args) # Connection lost
                # while Bitalino_Manager.connection_failed_counter < 5: # Attempt reconnection (upto 5 times)
                #     print("Attempting to re-connect.")
                #     # retry connecting to the device
                #     if Bitalino_Manager.connect(macAddress=macAddress,timeout=5) is True:
                #         print("Restarting aquisition.")
                #         Bitalino_Manager.start_aquisition(runtime=runtime, samplingRate=samplingRate, nSamples=nSamples, show_live_plot=show_live_plot, save_to_file=save_to_file)
                #         break
                # Bitalino_Manager.connection_failed_counter = 0
                
            elif str(e) == str(BITalinoExceptionCode.DEVICE_NOT_IDLE):
                print("Error", e.args) # Host busy
                print("Interrupting device.")
                Bitalino_Manager.force_stop_aquisition()
                print("Restarting aquisition.")
                return Bitalino_Manager.start_aquisition(runtime=runtime, samplingRate=samplingRate, nSamples=nSamples, show_live_plot=show_live_plot, save_to_file=save_to_file)
            else : 
                print("Unhandeled Error : ", str(e))

        if show_live_plot is True:
            print("Terminate plot process")
            if p.poll() is None : # if the process is still running
                p.send_signal(signal.SIGINT) # Send Ctrl + C
        
        # Script sleeps for n seconds
        time.sleep(1)

        # Stop acquisition
        Bitalino_Manager.force_stop_aquisition()

        # Disconnect device
        Bitalino_Manager.disconnect()

        # save session data for later analysis (useful while using jupyter notebook)
        Bitalino_Manager.collected_data[sesssion_time_stamp] = collected_data_in_this_session

        # save session data to file
        if save_to_file:
            df = pd.DataFrame(collected_data_in_this_session)
            # Check if the directory exists, if not, create it
            directory = 'data/bitalino/'
            if not os.path.exists(directory): os.makedirs(directory)
            path = os.path.join(directory, f"{file_name_prefix}_AQ_FS_{Bitalino_Manager.device_state.sampling_rate}_TS_{sesssion_time_stamp}.csv")
            df.to_csv(path,index=False)

        
        return sesssion_time_stamp, collected_data_in_this_session
        
    # Set battery threshold. 
    # The factory default value is 0 (which is equivalent to 3.4 V). It is used to indicate low battery through red LED on Bitalino.
    # def set_battery_threshold(thresh):
    #     Bitalino_EDA.device.battery(thresh)
        
    def force_stop_aquisition():
        # Stop acquisition
        Bitalino_Manager.device.stop()
        print("Acquisition Stopped.")

    def print_collected_data():
        df = pd.DataFrame(Bitalino_Manager.collected_data)
        print(df.to_markdown())

