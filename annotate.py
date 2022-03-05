import argparse
import json
import os
import random

from PyQt5 import QtGui, QtCore
import sys

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QPushButton,
    QGridLayout,
    QWidget,
    QLabel,
)


class AnnotationWidget(QWidget):
    def __init__(self, args):
        super().__init__()
        self.images_path = args.images_path
        self.num_samples = args.num_samples
        self.output_file = args.output_file
        if os.path.isfile(self.output_file):
            QMessageBox.warning(
                self,
                "Warning",
                f"Output file {self.output_file} exists already! Either move this file or specify another "
                f"location using the --output-file argument.",
            )
            self.close()
            sys.exit()

        self.results = []

        self.input_file = args.input_file
        print("Loading: ", self.input_file)
        self.samples = json.load(open(self.input_file, "r"))
        print("Done.")

        self.indices = random.sample(range(len(self.samples)), args.num_samples)
        self.target_positions = random.choices([0, 1], k=args.num_samples)

        grid = QGridLayout()
        self.setLayout(grid)

        self.text_title = QLabel(self)
        self.text_title.setFixedHeight(30)
        self.text_title.setFont(QFont("Arial", 10))
        self.text_title.setAlignment(QtCore.Qt.AlignRight)
        grid.addWidget(self.text_title, 0, 0, 1, 2)

        self.picture = QLabel(self)
        self.picture.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self.picture, 1, 0, 1, 2)
        self.picture.show()

        self.text_question = QLabel(self)
        self.text_question.setFixedHeight(15)
        self.text_question.setAlignment(QtCore.Qt.AlignCenter)
        self.text_question.setText("Which phrase describes the image better?")
        grid.addWidget(self.text_question, 3, 0, 1, 2)

        self.button_left = QPushButton("left")
        self.button_left.clicked.connect(self.choose_left)
        grid.addWidget(self.button_left, 4, 0)

        self.button_right = QPushButton("right")
        self.button_right.clicked.connect(self.choose_right)
        grid.addWidget(self.button_right, 4, 1)

        self.setWindowTitle("Annotate")

        self.sample_index = -1
        self.next_sample()

        self.show()

    def plot_sample(self):
        title_text = f"sample {self.sample_index+1}/{self.num_samples}"
        self.text_title.setText(title_text)

        text_target, text_distractor = self.sample["sentence_target"], self.sample["sentence_distractor"]

        if self.target_positions[self.sample_index] == 0:
            self.button_left.setText(text_target)
            self.button_right.setText(text_distractor)
        else:
            self.button_left.setText(text_distractor)
            self.button_right.setText(text_target)

        img_path = os.path.join(self.images_path, self.sample["img_filename"])
        pixmap = QtGui.QPixmap(img_path)
        pixmap = pixmap.scaledToWidth(800)
        if pixmap.height() > 600:
            pixmap = pixmap.scaledToHeight(600)
        self.picture.setPixmap(pixmap)

    def next_sample(self):
        self.sample_index += 1

        self.save()
        if self.sample_index >= self.num_samples:
            self.save()
            QMessageBox.information(
                self,
                "End",
                f"End of annotation. The results have been saved to {self.output_file}."
                "\nThanks for your help!",
            )
            self.close()
            sys.exit()

        self.sample = self.samples[self.indices[self.sample_index]]

        self.plot_sample()

    def choose_left(self):
        result = self.sample
        result["result"] = self.target_positions[self.sample_index] == 0
        self.results.append(result)
        self.next_sample()

    def choose_right(self):
        result = self.sample
        result["result"] = self.target_positions[self.sample_index] == 1
        self.results.append(result)
        self.next_sample()

    def save(self):
        json.dump(self.results, open(self.output_file, "w"))


def parse_args():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--input-file", type=str, required=True,
    )
    argparser.add_argument(
        "--output-file", type=str, default="samples_annotated.json",
    )
    argparser.add_argument(
        "--num-samples", type=int, default=100,
    )
    argparser.add_argument(
        "--images-path", type=str, default=os.path.expanduser("~/data/multimodal_evaluation/images/"),
    )

    args = argparser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    app = QApplication(sys.argv)
    ex = AnnotationWidget(args)
    sys.exit(app.exec_())
