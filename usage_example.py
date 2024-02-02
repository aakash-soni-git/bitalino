from Bitalinomanager import Bitalino_Manager

addr = "00:21:08:35:14:75"
print("Start Bitalino Data Aquisition...")
Bitalino_Manager.start_aquisition(channels={'A1':'EDA', 'A2':'ECG'},
    samplingRate=100, 
    nSamples=100,
    runtime=10, 
    show_live_plot=True,
    save_to_file=True,
    print_sample_log=False,
    macAddress=addr)
