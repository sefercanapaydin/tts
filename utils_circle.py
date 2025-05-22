import numpy as np
import matplotlib
matplotlib.use('Agg')   # GUI backend yerine dosya üretimine uygun backend
import matplotlib.pyplot as plt
from noise import snoise2
import os
import string
import random



def save_circle_with_text_to_images(file_name, text, size=1024, scale=0.25, octaves=1,
                                   fontname="DejaVu Sans", fontsize=None, fontcolor='white', bold=True
                            ):
    # images/ klasörünü oluştur
    images_dir = "images"
    os.makedirs(images_dir, exist_ok=True)

    # Random dosya adı oluştur
    filename = file_name
    filepath = os.path.join(images_dir, filename)

    # Çember ve noise oluştur
    x, y = np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size))
    mask = x**2 + y**2 <= 1

    seed = np.random.randint(0, 10000)
    noise_map = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            nx, ny = x[i, j] * scale, y[i, j] * scale
            noise_map[i, j] = snoise2(nx + seed, ny + seed, octaves=octaves, base=seed)
    noise_map = (noise_map - noise_map.min()) / (noise_map.max() - noise_map.min())
    cmap = plt.get_cmap('rainbow')
    rgba_img = cmap(noise_map)
    rgba_img[..., 3] = mask

    dpi = 100
    fig, ax = plt.subplots(figsize=(size/dpi, size/dpi), dpi=dpi)
    ax.imshow(rgba_img)
    ax.axis('off')

    if fontsize is None:
        fontsize = size // 15
    fontweight = 'bold' if bold else 'normal'
    ax.text(0.5, 0.5, text, color=fontcolor,
            fontsize=fontsize, fontname=fontname, fontweight=fontweight,
            ha='center', va='center', transform=ax.transAxes)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(filepath, transparent=True, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    print(f"Görsel '{filename}' olarak images/ klasörüne kaydedildi.")


