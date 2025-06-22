import tkinter as tk

from .app import VideoLabelingApp

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoLabelingApp(root)
    root.mainloop()
