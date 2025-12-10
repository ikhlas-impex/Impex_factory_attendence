import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from PIL import Image, ImageTk


class CapturedPhotosWindow(tk.Toplevel):
    """Window to manage captured photos"""

    def __init__(self, parent, captured_photos):
        super().__init__(parent)
        self.title("Captured Photos")
        self.geometry("600x400")
        self.transient(parent)
        self.captured_photos = captured_photos

        self.listbox = tk.Listbox(self, height=15)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text="👁 View", command=self.view_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 Save", command=self.save_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑 Clear", command=self.clear_photos).pack(side=tk.RIGHT, padx=5)

        self.update_photo_list()

    def update_photo_list(self):
        """Refresh the list of captured photos"""
        self.listbox.delete(0, tk.END)
        for photo in self.captured_photos:
            ts = photo.get('timestamp')
            label = ts.strftime('%Y-%m-%d %H:%M:%S') if ts else photo.get('filename', 'Photo')
            self.listbox.insert(tk.END, label)

    def get_selected_photo(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Select Photo", "Please select a photo first.")
            return None
        return self.captured_photos[selection[0]]

    def view_photo(self):
        """Open selected photo in a new window"""
        photo = self.get_selected_photo()
        if not photo:
            return
        frame_rgb = cv2.cvtColor(photo['frame'], cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        viewer = tk.Toplevel(self)
        viewer.title(photo.get('filename', 'Photo'))
        imgtk = ImageTk.PhotoImage(img)
        label = tk.Label(viewer, image=imgtk)
        label.image = imgtk  # Keep reference
        label.pack()

    def save_photo(self):
        """Save selected photo to disk"""
        photo = self.get_selected_photo()
        if not photo:
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension='.jpg',
            initialfile=photo.get('filename', 'capture.jpg'),
            filetypes=[("JPEG Image", "*.jpg"), ("PNG Image", "*.png")]
        )
        if file_path:
            try:
                cv2.imwrite(file_path, photo['frame'])
                messagebox.showinfo("Saved", f"Photo saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save photo: {e}")

    def clear_photos(self):
        """Clear all captured photos"""
        if not self.captured_photos:
            messagebox.showinfo("No Photos", "No photos to clear.")
            return
        if messagebox.askyesno(
            "Clear Photos", f"Delete all {len(self.captured_photos)} captured photos?"
        ):
            self.captured_photos.clear()
            self.update_photo_list()
