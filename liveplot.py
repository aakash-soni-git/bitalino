import matplotlib.pyplot as plt
import numpy as np
import sys
import json

# This script can be called with minimum 2 arguments along with the script name
# arg[0] => scriptname
# arg[1] => sampling frequency
# arg[2] => Plot label 1
# arg[3] => Plot label 2 ...
# Example : python3 liveplot.py 1000 EDA ecg
if len(sys.argv) > 2 :
    # Retrieve arguments passed by the parent process
    args = sys.argv[1:]  # Exclude the first argument, which is the script filename
    # Print the received arguments
    print("Child received arguments:", args[0])
    fs = int(args[0]) # sampling frequency
    labels = args[1:] # sampling frequency

    fig = plt.figure()
    ax = [fig.add_subplot(len(labels), 1, i+1) for i in range(len(labels))] # list of axes
    top = -1000
    bottom = 1000

else: 
    raise Exception("Missing arguments : sampling frequency, label1, label2, ...")

# Update plot with the data
# Data : [[Sensor_1 flatten data], [Sensor_2 flatten data], ...]
def update_plot(data): 
    global fig # It must be global
    global ax # It must be global
    global top # It must be global
    global bottom # It must be global
    global fs # This is initialised by sys.argv
    global labels # This is initialised by sys.argv
    
    # Add x and y to lists
    nb_datapoints = int(10*fs) # plot only last 10 sec data
    # data = _collected_data_np_array = np.array(list(collected_data_in_this_session.values())) # to facilitate manipulation
    data = np.array(list(data))
    ys = data[:,-nb_datapoints:]
    # xs.append(dt.datetime.now().strftime('%H:%M:%S.%f'))
    xs = np.arange(max(0,data.shape[1] - nb_datapoints), data.shape[1]) # x-values = indices

    for i in range(len(ys)) :
        ax[i].clear()
        ax[i].plot(xs, ys[i], label=f"{labels[i]}")
        ax[i].legend(loc='upper right')

        # Format plot
        top = np.max(ys[i]) # max(np.max(ys[i]), top)
        bottom = np.min(ys[i]) # min(np.min(ys[i]), bottom)
        ax[i].set_ylim(top=top,bottom=bottom)
        # ax[i].set_xticklabels(rotation=45, ha='right') # for some reason, this is crashing
        ax[i].set_ylabel('Aux unit')
    plt.subplots_adjust(bottom=0.30)
    plt.suptitle('Live Sensor Data (last 10 sec)')
    plt.xlabel("Sample #")
    plt.legend()

    plt.pause(0.5)

def close():
    plt.close()

try:
    while True:
        # Read the message sent by the parent process from stdin
        arr_json = sys.stdin.readline().strip() # wait for message (it contais list of flattened list per sensor data)
        arr = np.array(json.loads(arr_json)) # Convert the JSON string back to a NumPy array
        update_plot(data=arr)

except KeyboardInterrupt :
    print("Keyboard Interrupt [Ctrl + c] in live plot.")
    close()

print("Exit Live Plot")
exit(0)