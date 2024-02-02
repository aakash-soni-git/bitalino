# bitalino
Python script to collect physiological data using Bitalino board sensors.

It allows:
- Collecting Data from 1 or more sensors (only analog channels A1, A2, ... A6)
- Plotting live sensor data. The live plot script is launched in a seperate subprocess to prevent freezing the GUI. \[do not use plt.show()\]
- Saving the results to a CSV file. 1 column per sensor. The output file name includes the time stamp.

[Dependencies :]
  Official Bitalino library : pip install bitalino
  https://github.com/BITalinoWorld/python-api

[Usage : ]
  See usage_example.py

[Test :]
  Tested on Kubuntu 22.04
  using BITalino PsychoBIT kit (https://www.pluxbiosignals.com/en-fr/collections/bitalino/products/psychobit)
  with EDA and ECG sensors.
