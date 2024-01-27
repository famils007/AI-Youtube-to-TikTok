import sys
import os
import random
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QFileDialog, QSlider, QMessageBox, QWidget, QCheckBox
from pytube import YouTube
from moviepy.editor import VideoFileClip, CompositeVideoClip, clips_array
import cv2
from AiSubtitles import convert_video_to_audiogram



class VideoProcessingThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, url1, url2, path, option, blur_strength, segment_length, segmentation_enabled, subtitles_enabled):
        super().__init__()
        self.url1 = url1
        self.url2 = url2
        self.path = path
        self.option = option
        self.blur_strength = blur_strength
        self.segment_length = segment_length
        self.segmentation_enabled = segmentation_enabled
        self.subtitles_enabled = subtitles_enabled


    def run(self):
        try:
            filename1 = self.download_video(self.url1)
            if not filename1:
                raise Exception("Failed to download the first video.")

            final_video_path = ""  # Variable to hold the path of the final video to segment

            if self.option == 1:
                final_video_path = self.process_video(filename1)
            elif self.option == 2 and self.url2:
                filename2 = self.download_video(self.url2)
                if not filename2:
                    raise Exception("Failed to download the second video.")
                final_video_path = self.combine_videos(filename1, filename2)

                # Call convert_video_to_audiogram conditionally
            if self.subtitles_enabled and final_video_path:
                final_video_path = convert_video_to_audiogram(final_video_path, self.option)

                # Proceed with segmentation if enabled
            if self.segmentation_enabled and final_video_path:
                self.split_video_into_segments(final_video_path)

            self.finished.emit("Download und Verarbeitung abgeschlossen.")
        except Exception as e:
            self.finished.emit(str(e))
    def download_video(self, url):
        print("Das Video wird heruntergeladen...")
        yt = YouTube(url)
        video_title = yt.title.replace(" ", "_").replace("/", "_")
        output_filename = os.path.join(self.path, f"{video_title}.mp4")
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        stream.download(filename=output_filename)
        return output_filename

    def blur_video_frame(self, frame):
        return cv2.GaussianBlur(frame, (self.blur_strength, self.blur_strength), 0)

    def process_video(self, filename):
        video = VideoFileClip(os.path.join(self.path, filename))
        w, h = video.size
        bg_height = int(w * 16 / 9)
        bg_size = (w, bg_height)
        blurred_clip = video.fl_image(self.blur_video_frame)
        if w / h < 9 / 16:
            crop_height = int(w * 16 / 9)
            blurred_clip = blurred_clip.crop(y_center=h / 2, height=crop_height)
        else:
            crop_width = int(h * 9 / 16)
            blurred_clip = blurred_clip.crop(x_center=w / 2, width=crop_width)
        blurred_clip = blurred_clip.resize(newsize=bg_size)
        cropped_video = video.crop(width=w, height=w * 9 / 16, x_center=w / 2, y_center=h / 2)
        final_video = CompositeVideoClip([blurred_clip.set_position(("center", "center")), cropped_video.set_position(("center", "center"))], size=bg_size)
        processed_video_path = os.path.join(self.path, "processed_video.mp4")  # Path of the processed video
        final_video.write_videofile(os.path.join(self.path, "processed_video.mp4"), preset="ultrafast", threads=200)
        return processed_video_path

    def combine_videos(self, first_video, second_video):
        video1_path = os.path.join(self.path, first_video)
        video2_path = os.path.join(self.path, second_video)
        output_path = os.path.join(self.path, "combined_video.mp4")

        video1 = VideoFileClip(video1_path)
        video2 = VideoFileClip(video2_path)

        w1, h1 = video1.size
        w2, h2 = video2.size

        if video2.duration > video1.duration:
            max_start = video2.duration - video1.duration
            start = random.uniform(0, max_start)
            video2 = video2.subclip(start, start + video1.duration)

        video1_resized = video1.crop(x1=w1 / 8, y1=0, x2=(w1 / 8) * 7, y2=h1)
        video2_resized = video2.crop(x1=w2 / 8, y1=0, x2=(w2 / 8) * 7, y2=h2)
        final_clip = clips_array([[video1_resized], [video2_resized]])
        combined_video_path = os.path.join(self.path, "combined_video.mp4")  # Path of the combined video
        final_clip.write_videofile(output_path, preset="ultrafast", threads=200)
        return combined_video_path

    def split_video_into_segments(self, video_path):
        video = VideoFileClip(video_path)
        duration = video.duration
        for start in range(0, int(duration), self.segment_length):
            end = min(start + self.segment_length, duration)
            segment = video.subclip(start, end)
            segment_path = f"{video_path}_segment_{start // self.segment_length}.mp4"
            segment.write_videofile(segment_path, preset="ultrafast", threads=200)


class YouTubeDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT to TT")
        self.blur_strength = 21
        self.segment_length = 60
        self.segmentation_enabled = True
        self.option = 1
        self.initUI()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        layout.addWidget(QLabel("Convert Youtube to TikTok with AI", self))

        self.createOptionFrame(layout)
        self.createUrlFrame(layout)
        self.createPathSelection(layout)
        self.createSegmentationControls(layout)

        self.subtitles_checkbox = QCheckBox("Activate Subtitles", self)
        self.subtitles_checkbox.setChecked(True)  # Default to checked
        layout.addWidget(self.subtitles_checkbox)

        self.download_button = QPushButton("Start Dowload and Processing", self)
        self.download_button.clicked.connect(self.download)
        layout.addWidget(self.download_button)

    def createOptionFrame(self, layout):
        option_frame = QWidget(self)
        option_layout = QVBoxLayout(option_frame)
        self.option1_rb = QRadioButton("Blurred Background", option_frame)
        self.option1_rb.toggled.connect(lambda: self.on_option_toggle(1))
        self.option2_rb = QRadioButton("Stack with Retention Clip (MC Jump n Run)", option_frame)
        self.option2_rb.toggled.connect(lambda: self.on_option_toggle(2))
        option_layout.addWidget(self.option1_rb)
        option_layout.addWidget(self.option2_rb)
        layout.addWidget(option_frame)

    def createUrlFrame(self, layout):
        url_frame = QWidget(self)
        url_layout = QVBoxLayout(url_frame)
        self.url_label1 = QLabel("First video Youtube URL:", url_frame)
        self.url_entry1 = QLineEdit(url_frame)
        self.url_label2 = QLabel("Retention video Youtube URL:", url_frame)
        self.url_entry2 = QLineEdit(url_frame)

        # Set a default value for the second URL
        self.url_entry2.setText("https://www.youtube.com/watch?v=NX-i0IWl3yg&t=11s")

        self.url_label2.hide()
        self.url_entry2.hide()
        url_layout.addWidget(self.url_label1)
        url_layout.addWidget(self.url_entry1)
        url_layout.addWidget(self.url_label2)
        url_layout.addWidget(self.url_entry2)
        layout.addWidget(url_frame)

    def createPathSelection(self, layout):
        self.path_label = QLabel("Work directory", self)
        self.path_entry = QLineEdit(self)
        self.browse_button = QPushButton("Choose work directory", self)
        self.browse_button.clicked.connect(self.browse_folder)
        layout.addWidget(self.path_label)
        layout.addWidget(self.path_entry)
        layout.addWidget(self.browse_button)

    def createSegmentationControls(self, layout):
        self.segmentation_checkbox = QCheckBox("Activate segmentation", self)
        self.segmentation_checkbox.setChecked(self.segmentation_enabled)
        self.segmentation_checkbox.stateChanged.connect(self.on_segmentation_checkbox_changed)
        self.segment_length_label = QLabel(f"Segmentation Length: {self.segment_length} seconds", self)
        self.segment_length_slider = QSlider(QtCore.Qt.Horizontal, self)
        self.segment_length_slider.setMinimum(60)
        self.segment_length_slider.setMaximum(240)
        self.segment_length_slider.setValue(self.segment_length)
        self.segment_length_slider.setTickInterval(30)
        self.segment_length_slider.setTickPosition(QSlider.TicksBelow)
        self.segment_length_slider.valueChanged.connect(self.on_segment_length_changed)
        self.segment_length_label.setVisible(self.segmentation_enabled)
        self.segment_length_slider.setVisible(self.segmentation_enabled)
        layout.addWidget(self.segmentation_checkbox)
        layout.addWidget(self.segment_length_label)
        layout.addWidget(self.segment_length_slider)

    def on_option_toggle(self, option_number):
        self.option = option_number
        self.url_label2.setVisible(option_number == 2)
        self.url_entry2.setVisible(option_number == 2)

    def on_segmentation_checkbox_changed(self, state):
        self.segmentation_enabled = state == QtCore.Qt.Checked
        self.segment_length_label.setVisible(self.segmentation_enabled)
        self.segment_length_slider.setVisible(self.segmentation_enabled)

    def on_segment_length_changed(self, value):
        self.segment_length = value
        self.segment_length_label.setText(f"Segmentation Length: {value} seconds")

    def download(self):
        url1 = self.url_entry1.text()
        url2 = self.url_entry2.text() if self.option == 2 else ""
        path = self.path_entry.text()

        if not url1 or not path:
            QMessageBox.warning(self, "Warning", "Please choose at least one URL and specify a directory")
            return

        subtitles_enabled = self.subtitles_checkbox.isChecked()

        self.thread = VideoProcessingThread(url1, url2, path, self.option, self.blur_strength, self.segment_length,
                                            self.segmentation_enabled, subtitles_enabled)
        self.thread.finished.connect(self.on_download_finished)
        self.thread.start()

    def on_download_finished(self, message):
        QMessageBox.information(self, "Info", message)

    def browse_folder(self):
        folder_selected = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder_selected:
            self.path_entry.setText(folder_selected)

    def blur_video_frame(self, frame):
        return cv2.GaussianBlur(frame, (self.blur_strength, self.blur_strength), 0)

def main():
    app = QApplication(sys.argv)
    ex = YouTubeDownloaderApp()
    ex.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()