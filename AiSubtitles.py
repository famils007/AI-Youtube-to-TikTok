# execute the following before starting:
# pip install --quiet ipython-autotime
# pip install ffmpeg-python==0.2.0
# pip install git+https://github.com/openai/whisper.git@248b6cb124225dd263bb9bd32d060b6517e067f8
# pip install moviepy==2.0.0.dev2
# pip install imageio==2.25.1
#pip install opencv-python
#pip install PyQt5
#pip install pytube

# Import necessary libraries
import os
import json
import ffmpeg
import whisper
from moviepy.editor import TextClip, CompositeVideoClip, VideoFileClip

def convert_video_to_audiogram(videofilename, option):
    # Extract audio from the video file
    audiofilename = videofilename.replace(".mp4", '.mp3')
    input_stream = ffmpeg.input(videofilename)
    audio = input_stream.audio
    output_stream = ffmpeg.output(audio, audiofilename)
    output_stream = ffmpeg.overwrite_output(output_stream)
    ffmpeg.run(output_stream)
    print(audiofilename)

    # Load the video to get its dimensions
    input_video = VideoFileClip(videofilename)
    input_video_duration = input_video.duration

    # Get the dimensions of the video
    frame_width, frame_height = input_video.size
    frame_size = (frame_width, frame_height)  # Use the actual video size

    # Get word-level transcription from audio
    model = whisper.load_model("small")
    result = model.transcribe(audiofilename, word_timestamps=True)
    print(result)

    # Process the transcription
    wordlevel_info = []
    for each in result['segments']:
        words = each['words']
        for word in words:
            wordlevel_info.append({'word': word['word'].strip(), 'start': word['start'], 'end': word['end']})

    # Store word-level timestamps into JSON file
    with open('data.json', 'w') as f:
        json.dump(wordlevel_info, f, indent=4)

    # Load the JSON file
    with open('data.json', 'r') as f:
        wordlevel_info_modified = json.load(f)

    # Function to split text into lines
    def split_text_into_lines(data):
        MaxChars = 25
        # maxduration in seconds
        MaxDuration = 3.0
        # Split if nothing is spoken (gap) for these many seconds
        MaxGap = 1.5

        subtitles = []
        line = []
        line_duration = 0
        line_chars = 0

        for idx, word_data in enumerate(data):
            word = word_data["word"]
            start = word_data["start"]
            end = word_data["end"]

            line.append(word_data)
            line_duration += end - start

            temp = " ".join(item["word"] for item in line)

            # Check if adding a new word exceeds the maximum character count or duration
            new_line_chars = len(temp)

            duration_exceeded = line_duration > MaxDuration
            chars_exceeded = new_line_chars > MaxChars
            if idx > 0:
                gap = word_data['start'] - data[idx - 1]['end']
                # print (word,start,end,gap)
                maxgap_exceeded = gap > MaxGap
            else:
                maxgap_exceeded = False

            if duration_exceeded or chars_exceeded or maxgap_exceeded:
                if line:
                    subtitle_line = {
                        "word": " ".join(item["word"] for item in line),
                        "start": line[0]["start"],
                        "end": line[-1]["end"],
                        "textcontents": line
                    }
                    subtitles.append(subtitle_line)
                    line = []
                    line_duration = 0
                    line_chars = 0

        if line:
            subtitle_line = {
                "word": " ".join(item["word"] for item in line),
                "start": line[0]["start"],
                "end": line[-1]["end"],
                "textcontents": line
            }
            subtitles.append(subtitle_line)

        return subtitles

    # Convert word-level timestamps JSON to line-level timestamps JSON
    linelevel_subtitles = split_text_into_lines(wordlevel_info_modified)

    # Function to create caption
    def create_caption(textJSON, framesize, font="font.ttf", fontsize=55, color='white', bgcolor='red'):
        wordcount = len(textJSON['textcontents'])
        full_duration = textJSON['end'] - textJSON['start']

        word_clips = []
        xy_textclips_positions = []

        x_pos = 0
        y_pos = 0
        frame_width = framesize[0]
        frame_height = framesize[1]
        subtitle_width = frame_width * 0.9  # Subtitles take up 80% of the video width
        x_buffer = (frame_width - subtitle_width) / 2  # Centering subtitles horizontally
        # Adjust y_buffer based on the option
        if option == 1:  # Blurred Background
            y_buffer = frame_height * 2 / 3
        else:  # Stack with Retention Clip
            y_buffer = frame_height * 1 / 2

        space_width = ""
        space_height = ""

        for index, wordJSON in enumerate(textJSON['textcontents']):
            duration = wordJSON['end'] - wordJSON['start']
            word_clip = TextClip(wordJSON['word'], font=font, fontsize=fontsize, color=color, stroke_color='black',
                                 stroke_width=3).set_start(
                textJSON['start']).set_duration(full_duration)  # Added stroke_color and stroke_width
            word_clip_space = TextClip(" ", font=font, fontsize=fontsize, color=color, stroke_color='black',
                                       stroke_width=3).set_start(
                textJSON['start']).set_duration(full_duration)  # Added stroke_color and stroke_width
            word_width, word_height = word_clip.size
            space_width, space_height = word_clip_space.size
            if x_pos + word_width + space_width > subtitle_width:
                # Move to the next line
                x_pos = 0
                y_pos += word_height + 10  # Adjust line spacing if needed

            # Store info of each word_clip created
            xy_textclips_positions.append({
                "x_pos": x_pos + x_buffer,
                "y_pos": y_pos + y_buffer,
                "width": word_width,
                "height": word_height,
                "word": wordJSON['word'],
                "start": wordJSON['start'],
                "end": wordJSON['end'],
                "duration": duration
            })

            word_clip = word_clip.set_position((x_pos + x_buffer, y_pos + y_buffer))
            word_clip_space = word_clip_space.set_position((x_pos + word_width + x_buffer, y_pos + y_buffer))
            x_pos += word_width + space_width

            word_clips.append(word_clip)
            word_clips.append(word_clip_space)

        for highlight_word in xy_textclips_positions:
            word_clip_highlight = TextClip(highlight_word['word'], font=font, fontsize=fontsize, color=color, stroke_color='black', stroke_width=3, bg_color=bgcolor).set_start(highlight_word['start']).set_duration(highlight_word['duration'])  # Added stroke_color and stroke_width
            word_clip_highlight = word_clip_highlight.set_position((highlight_word['x_pos'], highlight_word['y_pos']))
            word_clips.append(word_clip_highlight)

        return word_clips

        # Create an audiogram with word-level highlights

    all_linelevel_splits = []
    for line in linelevel_subtitles:
        out = create_caption(line, frame_size)  # Pass the actual video size
        all_linelevel_splits.extend(out)

    background_clip = input_video
    final_video = CompositeVideoClip([background_clip] + all_linelevel_splits)
    final_video = final_video.set_audio(input_video.audio)

    # Generate output file path in the same directory as the input video
    output_dir = os.path.dirname(videofilename)
    output_filename = "subbed_" + os.path.basename(videofilename)
    output_filepath = os.path.join(output_dir, output_filename)

    # Save the final video to the generated path
    final_video.write_videofile(output_filepath, fps=24, preset="ultrafast", threads=200)

    print("Video saved to:", output_filepath)

    return output_filepath  # Add this line to return the path of the processed video



