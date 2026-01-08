#Client code

import datetime
import socket
import time
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

dirname = os.path.dirname(__file__)
os.chdir(dirname)
# Initialize plotting libraries
from OC import OC

def gaussian(x, amplitude, mean, stddev):
    return amplitude * np.exp(-(((x - mean) / stddev) ** 2) / 2)

#%%
# Check if connection to oven works
usb_port = "COM4"
try:
    oven = OC(usb_port)
    print("Connected to oven")
    print(oven.get_temperature())
except Exception as e:
    print(f"Caught exception: {e}.")
finally:
    print("Closing oven")
    oven.OC_close()

#%% Generic echo client
host = '141.255.216.54'
port = 65432  # The port used by the server
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))
    s.sendall(b"Hello, world")
    data = s.recv(1024)

print(f"Received {data!r}")
#%% Temp scan parameters
#temperature scan:
temperature_start = 43
temperature_end = 46
temperature_step = 0.01  # Was 0.1 initially, maybe it will not be as stable

exposure_time_TT = 60
sleepy_sleepy_oven = 15

n = (
     abs(int((temperature_end - temperature_start) / temperature_step)) + 1
 )  # +1 because of the initial temperature


# do you want to see the current status of the measurement?
print(f"Temperature scan will be performed from {temperature_start}-{temperature_end}.")
print("The scan will make ", n, " steps.")
print(
    "If everything goes according to plan, the scan will take approx. ",
    (exposure_time_TT * n + (2 * n * sleepy_sleepy_oven)) / (60 * 60),
    " h",
)

# data files
t = time.localtime()

data_file_name = (
    "Data/"
    + str(datetime.date.today())
    + "_SPDC_1560_phase_matching_fine_tsweep_"
    + str(temperature_start)
    + "-"
    + str(temperature_end)
    + "degC.data"
)

print(f"File name of new data is: {data_file_name}")

f = open(data_file_name, "a")
f.write("# Checking with better coupling in analysis stage, \"https://discord.com/channels/1013441055217156137/1092356277927161907/1392131089555787887\".\n")
f.write(f"# Temperature scan between {temperature_start} and {temperature_start} °C\n")
f.write(
    "# This measurement DOES include the coincidence stage and a DWDM where we separate single photons based on polarization and wavelength per channel.\n"
)
f.write("# --------------------------------- \n")
f.write("# Input laser power: 4.2 mW  at 780 nm (98 mA) \n")
f.write("# Power at input: - mW  at 780 nm (98 mA) \n")
f.write("# Pump polarization: 'D' (21R) = 2.85 mW)")
f.write("# Periodic polling: 19,65 um\n")
f.write("# Initial setup alignment at 44.087 C\n")
f.write(f"# Integration time:  {exposure_time_TT} s \n")
# f.write("# Single photon detector QE: 10, 10 % \n")
f.write("# Single photon detector QE: 85, 90, 86, 82% \n")
# f.write("# Single photon detector dead time: 5, 5 us \n")
f.write("# Single photon detector dead time: -20, -20, 20.38, 29.27 ns \n")
f.write("# ---------------------------------- \n")
f.write("# Temperature,Clicks1,Clicks2,Clicks3,Clicks4,Coincidances\n")
f.write("# [°C],[/],[/],[/],[/],[/]\n")

f.close()

#%% Client code 
# TODO: Collect certain channels only, currently hard coded to channels 1-4.
#       Collect correct coincidences. 1/2, 1/3, 1/4, 2/3, 2/4, 3/4
#       Set up server shutdown. [DONE]
#       Set up server run when client is on.
def client(hn: str, port: int, exposure_time_TT: float):
    host = hn  # The server's hostname or IP address
    port = port  # The port used by the server

    temperatures = np.linspace(temperature_start, temperature_end, n)
    
    sleepy_sleepy_oven = 10
    command = f"EXPOSURE{exposure_time_TT}"
    command = command.encode(encoding="utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(command)
    
    try:
        for temp in temperatures:
            usb_port = "COM4"
            oven = OC(usb_port)
            oven.set_temperature(round(temp,2))
            stability_oven = False

            # Stability check
            print("current set T: = ", round(temp, 2), " C")
            while stability_oven == False:
                time.sleep(sleepy_sleepy_oven)
                print("current T = ", oven.get_temperature(), " C")
                if abs(oven.get_temperature() - temp) < 0.01:
                    stability_oven = True
                    oven.OC_close()
                    print("Temperature stable, starting a measurement.")
                
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((host, port))
                    s.sendall(b"GATHER DATA")
                    data = s.recv(1024).decode("utf-8")
                    print(f"Current time is: {time.strftime('%H:%M:%S', time.localtime())}")
                    print(f"Temperature: {temp}, Received: {data}")
                    
                    # Check if the received data is an error message or a close oven message
                    if "Error" in data:
                        print(f"Error received from server: {data}")
                        file = open(data_file_name, "a")
                        file.write(f"{temp} Error: {data}\n")
                        file.close()
                        break
                    
                    # Parse the received data
                    parts = data.split(", ")
                    clicks1 = parts[0].split(": ")[1]
                    clicks2 = parts[1].split(": ")[1]
                    clicks3 = parts[2].split(": ")[1]
                    clicks4 = parts[3].split(": ")[1]
                    coincidences12 = parts[4].split(": ")[1]
                    coincidences13 = parts[5].split(": ")[1]
                    coincidences23 = parts[6].split(": ")[1]
                    coincidences14 = parts[7].split(": ")[1]
                    coincidences24 = parts[8].split(": ")[1]
                    coincidences34 = parts[9].split(": ")[1]

            # Write data to file
                    f = open(data_file_name, "a")
                    f.write(f"{round(temp,3)},{clicks1},{clicks2},{clicks3},{clicks4},{coincidences12},{coincidences13},{coincidences23},{coincidences14},{coincidences24},{coincidences34}\n")
                    f.close()
    except Exception as e:
            oven.set_temperature(42.15)
            print("I am here now, cunt.")
            oven.OC_close()
            print(f"An exception has occured: {e}.")
            
    print("Finishing the scan")
    oven.OC_close()
    print("Oven closed.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(b"STOP")
            data = s.recv(1024).decode("utf-8")
            print(f"Received: {data}")
#%%
# Run client at certain time
now = datetime.datetime.now()
runtime = now.replace(hour=12, minute=16, second=0, microsecond=0)

delay_seconds = (runtime-now).total_seconds()
delay_in_hours = delay_seconds/3600
hour = int(delay_in_hours)
mins = (delay_in_hours - hour) * 60
minutes = int(mins)
seconds = int((mins - minutes)*60)

print(f"The program will run at {runtime.time()} in {hour} hours, {minutes} minutes, and {seconds} seconds.")

time.sleep(delay_seconds)
# Just run the scan
host = '141.255.216.54'
port = 65432  # The port used by the server
start_time = time.perf_counter()
client(host, port, exposure_time_TT)
oven = OC("COM4")
oven.set_temperature(42)
oven.OC_close()
print(f"Time = {time.perf_counter()-start_time}")

#%% testing the server
host = '141.255.216.110'
port = 65432  # The port used by the server
start_time = time.perf_counter()
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(b"STOP")
        data = s.recv(1024).decode("utf-8")
        print(f"Received: {data}")
print(f"Time = {time.perf_counter()-start_time}")
#%% Checking fluctuations of singles and coincidences in time while keeping temperature constant for 1 minute or so, should be on the order of sqrt(N)
# # Read the data from the file, skipping rows starting with #
test_file = "Data/2025-07-22_SPDC_1560_phase_matching_fine_tsweep_41-46degC.data"

temperature = ["Temperature"]
singles = ["Clicks1", "Clicks2", "Clicks3", "Clicks4"]
coincidences = ["Coincidences12", "Coincidences13", "Coincidences23", "Coincidences14", "Coincidences24", "Coincidences34"]
snc = singles + coincidences
column_names = temperature + singles + coincidences


# Read file
dt = pd.read_csv(data_file_name, delimiter=',', comment="#", names=column_names, encoding="latin-1")
mean_of_singles_ch1 = np.mean(dt["Clicks1"])
std_of_singles_ch1 = np.std(dt["Clicks1"])


# Normalize
maxSS, minSS = dt[singles].max().max(), dt[singles].min().min()
maxCC, minCC = dt[coincidences].max().max(), dt[coincidences].min().min()

for name in singles:
    dt[f"Normalized{name}"] = (dt[name] - minSS) / (maxSS - minSS)
    dt[f"Rate{name}"] = dt[name] / exposure_time_TT
for name in coincidences:
    dt[f"Normalized{name}"] = (dt[name]  - minCC) / (maxCC - minCC)
    dt[f"Rate{name}"] = dt[name] / exposure_time_TT

# Create 2x2 subplots
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 15))
x = dt["Temperature"]

# Top row: Normalized
for name in singles:
    ax1.plot(x, dt[f"Normalized{name}"], label=f"{name}")
for name in coincidences:
    ax2.plot(x, dt[f"Normalized{name}"], label=f"{name}")

# Bottom row: Raw (rate)
for name in singles:
    ax3.plot(x, dt[f"Rate{name}"], label=f"{name}")
for name in coincidences:
    ax4.plot(x, dt[f"Rate{name}"], label=f"{name}")

# Gaussian fitting on normalized coincidences
fit_results = {}
for name in coincidences:
    y = dt[f"Normalized{name}"]
    try:
        popt, _ = curve_fit(gaussian, x, y, p0=[1, x.mean(), x.std()])
        fit_results[name] = popt
        ax2.plot(x, gaussian(x, *popt), '--', label=f"Fit {name} μ={popt[1]:.3f}")
    except RuntimeError:
        print(f"Fit failed for {name}")

# Format all plots
axes = [ax1, ax2, ax3, ax4]
titles = ["Normalized Singles", "Normalized Coincidences", "Raw Singles (Rate)", "Raw Coincidences (Rate)"]
ylabels = ["Normalized", "Normalized", "Counts/s", "Counts/s"]

for ax, title, ylabel in zip(axes, titles, ylabels):
    ax.set_title(title)
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel(ylabel)
    ax.legend()
    ax.grid(True)

plt.tight_layout()
plt.show()

#%% ALL of the plots
import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

# Gaussian model
def gaussian(x, amp, mu, sigma):
    return amp * np.exp(-(x - mu)**2 / (2 * sigma**2))

# Config
data_folder = "./Data"  # <- set this
file_pattern = "*.data"
# exposure_time_TT = 1  # <- set this

# Columns
temperature = ["Temperature"]
singles = ["Clicks1", "Clicks2", "Clicks3", "Clicks4"]
coincidences = ["Coincidences12", "Coincidences13", "Coincidences23", "Coincidences14", "Coincidences24", "Coincidences34"]
column_names = temperature + singles + coincidences

# Output
output_dir = "fit_outputs"
os.makedirs(output_dir, exist_ok=True)

# Batch processing
for file_path in glob.glob(os.path.join(data_folder, file_pattern)):

    # base_name = os.path.basename(file_path).replace(".csv", "")
    # print(f"Processing {base_name}...")
    print(f"Processing {file_path}...")

    # Read and normalize
    dt = pd.read_csv(file_path, delimiter=",", comment="#", names=column_names, encoding="latin-1")
    maxSS, minSS = dt[singles].max().max(), dt[singles].min().min()
    maxCC, minCC = dt[coincidences].max().max(), dt[coincidences].min().min()

    for name in singles:
        dt[f"Normalized{name}"] = (dt[name] / exposure_time_TT - minSS) / (maxSS - minSS)
    for name in coincidences:
        dt[f"Normalized{name}"] = (dt[name] / exposure_time_TT - minCC) / (maxCC - minCC)

    # Plot setup
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 15))
    x = dt["Temperature"]

    # Normalized singles
    for name in singles:
        ax1.plot(x, dt[f"Normalized{name}"], label=name)
        ax3.plot(x, dt[name] / exposure_time_TT, label=name)
    
    # Normalized coincidences + fits
    fit_results = []
    for name in coincidences:
        y_norm = dt[f"Normalized{name}"]
        y_raw = dt[name] / exposure_time_TT
        ax2.plot(x, y_norm, label=name)
        ax4.plot(x, y_raw, label=name)

        try:
            popt, _ = curve_fit(gaussian, x, y_norm, p0=[1, x.mean(), x.std()])
            y_fit = gaussian(x, *popt)
            r2 = r2_score(y_norm, y_fit)
            ax2.plot(x, y_fit, "--", label=f"Fit {name} μ={popt[1]:.2f}, R²={r2:.3f}")
            fit_results.append({
                "File": base_name,
                "Name": name,
                "Amplitude": popt[0],
                "Mean": popt[1],
                "StdDev": popt[2],
                "R2": r2
            })
        except RuntimeError:
            print(f"Fit failed for {name} in {base_name}")

    # Format
    for ax, ylabel, title in zip(
        (ax1, ax2, ax3, ax4),
        ("Normalized Singles", "Normalized Coincidences", "Raw Singles (Hz)", "Raw Coincidences (Hz)"),
        ("Normalized Singles vs Temperature", "Normalized Coincidences vs Temperature",
         "Raw Singles vs Temperature", "Raw Coincidences vs Temperature")):
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.grid(True)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{base_name}_plots.png"))
    plt.close()

    # Save fit results
    if fit_results:
        df_fit = pd.DataFrame(fit_results)
        df_fit.to_csv(os.path.join(output_dir, f"{base_name}_fit.csv"), index=False)

print("All files processed.")