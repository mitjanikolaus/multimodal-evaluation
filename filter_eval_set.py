import pickle

from PyQt5 import QtGui, QtCore
import sys

from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QPushButton,
    QGridLayout,
    QWidget,
    QLabel,
    QShortcut,
)

from generate_semantic_eval_sets_open_images import VERBS, SYNONYMS


class EvalSetFilter(QWidget):
    def __init__(self):
        super().__init__()

        self.input_file = "data/attribute-None.p"
        self.eval_sets = pickle.load(open(self.input_file, "rb"))

        for key, values in self.eval_sets.items():
            if len(values) > 0:
                print(f"{key}: {len(values)}")

        self.eval_sets_filtered = {key: [] for key in self.eval_sets.keys()}

        self.eval_set_index = 0
        self.eval_set_key = list(self.eval_sets.keys())[self.eval_set_index]

        while len(self.eval_sets[self.eval_set_key]) < 1:
            self.eval_set_index += 1
            self.eval_set_key = list(self.eval_sets.keys())[self.eval_set_index]

        self.eval_set = self.eval_sets[self.eval_set_key]
        print(f"{self.eval_set_key} ({len(self.eval_set)} examples)")

        self.sample_index = 0
        self.sample = self.eval_set[self.sample_index]

        grid = QGridLayout()
        self.setLayout(grid)

        self.text_title = QLabel(self)
        self.text_title.setFixedHeight(30)
        self.text_title.setFont(QFont("Arial", 20))
        self.text_title.setAlignment(QtCore.Qt.AlignCenter)
        grid.addWidget(self.text_title, 0, 0, 1, 2)

        self.pic_example = QLabel(self)
        grid.addWidget(self.pic_example, 1, 0)
        self.pic_counter_example = QLabel(self)
        grid.addWidget(self.pic_counter_example, 1, 1)

        self.text_example_target = QLabel(self)
        self.text_example_target.setFixedHeight(15)
        grid.addWidget(self.text_example_target, 2, 0)
        self.text_example_distractor = QLabel(self)
        self.text_example_distractor.setFixedHeight(15)
        grid.addWidget(self.text_example_distractor, 3, 0)
        self.text_example_filepath = QLabel(self)
        self.text_example_filepath.setFixedHeight(15)
        self.text_example_filepath.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        grid.addWidget(self.text_example_filepath, 4, 0)

        self.text_counterexample_target = QLabel(self)
        self.text_counterexample_target.setFixedHeight(15)
        grid.addWidget(self.text_counterexample_target, 2, 1)
        self.text_counterexample_distractor = QLabel(self)
        self.text_counterexample_distractor.setFixedHeight(15)
        grid.addWidget(self.text_counterexample_distractor, 3, 1)
        self.text_counterexample_filepath = QLabel(self)
        self.text_counterexample_filepath.setFixedHeight(15)
        self.text_counterexample_filepath.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        grid.addWidget(self.text_counterexample_filepath, 4, 1)

        self.plot_sample(self.sample)
        self.pic_example.show()
        self.pic_counter_example.show()
        self.text_example_target.show()
        self.text_example_distractor.show()
        self.text_example_filepath.show()
        self.text_counterexample_target.show()
        self.text_counterexample_distractor.show()
        self.text_counterexample_filepath.show()

        button_accept = QPushButton("accept (ctrl+a)")
        button_accept.clicked.connect(self.accept)
        grid.addWidget(button_accept, 5, 0)
        shortcut_accept = QShortcut(QKeySequence("Ctrl+A"), self)
        shortcut_accept.activated.connect(self.accept)

        button_reject = QPushButton("reject (ctrl+r)")
        button_reject.clicked.connect(self.reject)
        grid.addWidget(button_reject, 5, 1)
        shortcut_reject = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_reject.activated.connect(self.reject)

        button_reject_example = QPushButton("reject example (ctrl+e)")
        button_reject_example.clicked.connect(self.reject_example)
        grid.addWidget(button_reject_example, 6, 0)
        shortcut_reject = QShortcut(QKeySequence("Ctrl+E"), self)
        shortcut_reject.activated.connect(self.reject_example)

        button_next_eval_set = QPushButton("Go to next eval set")
        button_next_eval_set.clicked.connect(self.goto_next_eval_set)
        grid.addWidget(button_next_eval_set, 7, 0, 1, 2)

        button_save = QPushButton("Save filtered results")
        button_save.clicked.connect(self.save)
        grid.addWidget(button_save, 8, 0, 1, 2)

        self.setWindowTitle("Filter eval set")
        self.show()

    def plot_sample(self, sample):
        title_text = f"{self.eval_set_key} (sample {self.sample_index+1}/{len(self.eval_set)}) (eval set {self.eval_set_index+1}/{len(self.eval_sets)})"
        self.text_title.setText(title_text)

        # set rectangle colors and thicknesses
        penRectangleGreen = QtGui.QPen(QtCore.Qt.green)
        penRectangleGreen.setWidth(3)
        penRectangleRed = QtGui.QPen(QtCore.Qt.red)
        penRectangleRed.setWidth(3)
        penWhite = QtGui.QPen(QtCore.Qt.white)
        penWhite.setWidth(3)

        text_target = f"a {SYNONYMS[self.sample['relationship_target'].Label1][0]} {self.sample['relationship_target'].label} {SYNONYMS[self.sample['relationship_target'].Label2][0]}"
        if self.sample['relationship_target'].Label2 in VERBS:
            text_target += "ing"
        text_distractor = f"a {SYNONYMS[self.sample['counterexample_relationship_target'].Label1][0]} {self.sample['counterexample_relationship_target'].label} {SYNONYMS[self.sample['counterexample_relationship_target'].Label2][0]}"
        if self.sample['counterexample_relationship_target'].Label2 in VERBS:
            text_distractor += "ing"

        self.text_example_target.setText("Target: " + text_target)
        self.text_example_distractor.setText("Distractor: " + text_distractor)
        self.text_example_filepath.setText(self.sample['img_example'])

        self.text_counterexample_target.setText("Target: " + text_distractor)
        self.text_counterexample_distractor.setText("Distractor: " + text_target)
        self.text_counterexample_filepath.setText(self.sample['img_counterexample'])

        for img in [sample["img_example"], sample["img_counterexample"]]:
            pixmap = QtGui.QPixmap(img)
            pixmap = pixmap.scaledToWidth(550)

            # create painter instance with pixmap
            self.painterInstance = QtGui.QPainter(pixmap)

            relationships = [
                self.sample["relationship_target"],
                self.sample["relationship_visual_distractor"],
            ]
            if img == sample["img_counterexample"]:
                relationships = [
                    self.sample["counterexample_relationship_target"],
                    self.sample["counterexample_relationship_visual_distractor"],
                ]

            for relationship, pen in zip(
                relationships, [penRectangleGreen, penRectangleRed]
            ):
                bb = relationship.bounding_box

                # draw rectangle on painter
                self.painterInstance.setPen(pen)
                self.painterInstance.drawRect(
                    round(bb[0] * pixmap.width()),
                    round(bb[1] * pixmap.height()),
                    round(bb[2] * pixmap.width()),
                    round(bb[3] * pixmap.height()),
                )
                label = relationship.Label1 + f" ({relationship.Label2})"
                self.painterInstance.setPen(penWhite)
                self.painterInstance.drawText(
                    round(bb[0] * pixmap.width()), round(bb[1] * pixmap.height()), label
                )

            self.painterInstance.end()

            if img == sample["img_counterexample"]:
                self.pic_counter_example.setPixmap(pixmap)
            else:
                self.pic_example.setPixmap(pixmap)

    def reject_example(self):
        current_example = self.sample['img_example']
        while current_example == self.sample['img_example']:
            self.sample = self.get_next_sample()

        self.plot_sample(self.sample)

    def get_next_sample(self):
        self.sample_index += 1
        while self.sample_index >= len(self.eval_set):
            self.eval_set_index += 1
            if self.eval_set_index >= len(self.eval_sets.keys()):
                self.save()
                QMessageBox.information(
                    self,
                    "QMessageBox.information()",
                    "End of dataset, filtered everything!",
                )
                self.close()
                sys.exit()
            self.eval_set_key = list(self.eval_sets.keys())[self.eval_set_index]
            self.eval_set = self.eval_sets[self.eval_set_key]
            self.sample_index = 0
            print(f"finished eval set {self.eval_set_key}")

        sample = self.eval_set[self.sample_index]

        return sample

    def goto_next_eval_set(self):
        self.sample_index = 0

        self.eval_set_index += 1
        self.eval_set_key = list(self.eval_sets.keys())[self.eval_set_index]
        self.eval_set = self.eval_sets[self.eval_set_key]

        while self.sample_index >= len(self.eval_set):
            self.eval_set_index += 1
            if self.eval_set_index >= len(self.eval_sets.keys()):
                self.save()
                QMessageBox.information(
                    self,
                    "QMessageBox.information()",
                    "End of dataset, filtered everything!",
                )
                self.close()
                sys.exit()
            self.eval_set_key = list(self.eval_sets.keys())[self.eval_set_index]
            self.eval_set = self.eval_sets[self.eval_set_key]

        self.sample = self.eval_set[self.sample_index]
        self.plot_sample(self.sample)

    def accept(self):
        self.eval_sets_filtered[self.eval_set_key].append(self.sample)
        self.sample = self.get_next_sample()
        self.plot_sample(self.sample)

    def reject(self):
        self.sample = self.get_next_sample()
        self.plot_sample(self.sample)

    def save(self):
        pickle.dump(
            self.eval_sets_filtered,
            open(self.input_file.replace(".p", f"_filtered_sample_{self.sample_index}_eval_set_{self.eval_set_index}.p"), "wb"),
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = EvalSetFilter()
    sys.exit(app.exec_())
