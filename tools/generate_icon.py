from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 244, 244), radius=48, fill=(35, 42, 52, 255))
    draw.rounded_rectangle((43, 80, 213, 187), radius=20, fill=(74, 144, 226, 255))
    draw.rounded_rectangle((50, 61, 126, 101), radius=14, fill=(74, 144, 226, 255))

    nodes = [(86, 124), (128, 111), (169, 126), (108, 155), (151, 158)]
    links = [
        ((86, 124), (128, 111)),
        ((128, 111), (169, 126)),
        ((86, 124), (108, 155)),
        ((128, 111), (151, 158)),
        ((169, 126), (151, 158)),
        ((108, 155), (151, 158)),
    ]
    for start, end in links:
        draw.line((start, end), fill=(245, 248, 252, 255), width=7)
    for x, y in nodes:
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(245, 248, 252, 255))

    draw.line((166, 91, 176, 101), fill=(245, 248, 252, 255), width=6)
    draw.line((176, 101, 194, 79), fill=(245, 248, 252, 255), width=6)

    output = Path("assets") / "SmartOrganizer.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(output)


if __name__ == "__main__":
    main()
