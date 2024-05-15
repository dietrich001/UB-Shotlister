import pandas as pd
import subprocess
import os
from tkinter import Tk, filedialog, Button, Label, Entry, StringVar, StringVar, Frame
from tkinter.messagebox import showinfo
from tkinter import PhotoImage

def get_video_frame_rate(video_file):
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_file
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        r_frame_rate = result.stdout.decode().strip()
        num, den = map(int, r_frame_rate.split('/'))
        frame_rate = num / den
        return frame_rate
    except subprocess.CalledProcessError as e:
        print(f'Failed to get frame rate for {video_file}: {e}')
        print(f'STDERR: {e.stderr.decode()}')
        return None

def parse_edl(file_path, output_dir):
    # Read the file into a list of lines
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Parse the lines into a structured list
    data = []
    current_entry = []
    for line in lines:
        line = line.strip()
        # Skip irrelevant lines
        if not line or line.startswith("TITLE:") or line.startswith("FCM:"):
            continue
        # Check if the line is a clip name line
        if line.startswith("* FROM CLIP NAME:"):
            # This line contains the clip name, finalize the current entry
            clip_name = line.split(":")[1].strip()
            current_entry.append(clip_name)  # Add clip name to the current entry
            data.append(current_entry)  # Add the complete entry to the data list
            current_entry = []  # Reset for the next entry
        else:
            # This line contains timecode information, add it to the current entry
            parts = line.split()
            current_entry.extend(parts)

    # Filter out the unnecessary columns and rename 'Index' to 'Shot Number'
    filtered_data = []
    for entry in data:
        # Extract only the needed columns: Index (as Shot Number), Source In, Source Out, Promo In, Promo Out, Clip Name
        filtered_entry = [entry[0], entry[-1]] + entry[4:8]  # [Shot Number, Clip Name, Source In, Source Out, Promo In, Promo Out]
        filtered_data.append(filtered_entry)

    # Create the DataFrame with the new structure
    df = pd.DataFrame(filtered_data, columns=[
        'Shot Number', 'Clip Name', 'Source In', 'Source Out', 'Promo In', 'Promo Out'
    ])

    # Generate the CSV file name based on the EDL file name
    edl_filename = os.path.splitext(os.path.basename(file_path))[0]
    csv_file_name = f"{edl_filename}_shotlist.csv"
    csv_file_path = os.path.join(output_dir, 'shotlist', csv_file_name)

    # Ensure the shotlist directory exists
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    # Save the DataFrame to the CSV file
    df.to_csv(csv_file_path, index=False)

    return df, csv_file_path

def timecode_to_seconds(timecode, frame_rate):
    hours, minutes, seconds, frames = [int(part) for part in timecode.split(':')]
    return hours * 3600 + minutes * 60 + seconds + frames / frame_rate

def timecode_to_frames(timecode, frame_rate):
    hours, minutes, seconds, frames = [int(part) for part in timecode.split(':')]
    return ((hours * 3600 + minutes * 60 + seconds) * frame_rate) + frames

def frames_to_timecode(total_frames, frame_rate):
    frames = int(total_frames % frame_rate)
    seconds = int((total_frames // frame_rate) % 60)
    minutes = int((total_frames // (frame_rate * 60)) % 60)
    hours = int(total_frames // (frame_rate * 3600))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def adjust_promo_out_timecode(promo_out_timecode, frame_rate):
    total_frames = timecode_to_frames(promo_out_timecode, frame_rate)
    total_frames = total_frames - 1 if total_frames % frame_rate != 0 else total_frames
    return frames_to_timecode(total_frames, frame_rate)

def capture_screenshot(video_file, timecode, shot_number, clip_name, in_or_out, frame_rate, screenshot_dir):
    clean_clip_name = clip_name.replace(' ', '_').replace(',', '_').replace('.', '_')
    output_file = os.path.join(screenshot_dir, f'Shot{str(shot_number).zfill(2)}_{in_or_out}_{clean_clip_name}.png')
    time_in_seconds = timecode_to_seconds(timecode, frame_rate)

    command = [
        'ffmpeg',
        '-ss', str(time_in_seconds),
        '-i', video_file,
        '-frames:v', '1',
        '-q:v', '2',
        '-vf', 'scale=203:120',
        output_file
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f'Screenshot for {clean_clip_name} saved to {output_file}')
    except subprocess.CalledProcessError as e:
        print(f'Failed to capture screenshot for {clean_clip_name}: {e}')
        print(f'STDERR: {e.stderr.decode()}')

def process_edl_and_screenshots(edl_file, video_file, frame_rate, output_dir):
    edl_data, csv_file_path = parse_edl(edl_file, output_dir)
    screenshot_dir = os.path.join(output_dir, 'shotlist', 'screenshots')
    os.makedirs(screenshot_dir, exist_ok=True)

    for index, row in edl_data.iterrows():
        shot_number = row['Shot Number']
        clip_name = row['Clip Name']
        promo_in_timecode = row['Promo In']
        capture_screenshot(video_file, promo_in_timecode, shot_number, clip_name, "In", frame_rate, screenshot_dir)
        promo_out_timecode = adjust_promo_out_timecode(row['Promo Out'], frame_rate)
        capture_screenshot(video_file, promo_out_timecode, shot_number, clip_name, "Out", frame_rate, screenshot_dir)

    showinfo("Success", f"Processing completed successfully!\nParsed EDL saved as: {csv_file_path}")

def select_edl_file():
    edl_file_path.set(filedialog.askopenfilename(filetypes=[("EDL files", "*.edl"), ("All files", "*.*")]))

def select_video_file():
    video_file_path.set(filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]))
    frame_rate = get_video_frame_rate(video_file_path.get())
    if frame_rate:
        frame_rate_label.config(text=f"Frame rate is {frame_rate:.3f}", fg="red")

def select_output_directory():
    output_dir_path.set(filedialog.askdirectory())

# GUI setup
root = Tk()
root.title("UB Shotlister")

edl_file_path = StringVar()
video_file_path = StringVar()
output_dir_path = StringVar()
frame_rate = StringVar(value="23.976")

Label(root, text="EDL File:").grid(row=0, column=0, padx=10, pady=10)
Entry(root, textvariable=edl_file_path, width=50).grid(row=0, column=1, padx=10, pady=10)
Button(root, text="Browse", command=select_edl_file).grid(row=0, column=2, padx=10, pady=10)

Label(root, text="Video File:").grid(row=1, column=0, padx=10, pady=10)
Entry(root, textvariable=video_file_path, width=50).grid(row=1, column=1, padx=10, pady=10)
Button(root, text="Browse", command=select_video_file).grid(row=1, column=2, padx=10, pady=10)

Label(root, text="Frame Rate:").grid(row=2, column=0, padx=10, pady=10)
Entry(root, textvariable=frame_rate, width=50).grid(row=2, column=1, padx=10, pady=10)

Label(root, text="Output Directory:").grid(row=3, column=0, padx=10, pady=10)
Entry(root, textvariable=output_dir_path, width=50).grid(row=3, column=1, padx=10, pady=10)
Button(root, text="Browse", command=select_output_directory).grid(row=3, column=2, padx=10, pady=10)

Button(root, text="Make Shotlist!", command=lambda: process_edl_and_screenshots(edl_file_path.get(), video_file_path.get(), float(frame_rate.get()), output_dir_path.get())).grid(row=4, column=0, columnspan=3, padx=10, pady=20)

frame_rate_label = Label(root, text="", fg="red")
frame_rate_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

# Add company logo
logo_path = '/Users/jack.houston/Documents/programs/ub_screenshotter/versions/v6-gui/img/ub_logo.png'  # Path to your logo image file
logo_image = PhotoImage(file=logo_path)
logo_label = Label(root, image=logo_image, bg='#d8d7d7')
logo_label.grid(row=6, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()
