# Adapted from zhaobozhen/tgbot packages/shared/scripts/generate_libchecker_bundle.py
# Apache-2.0; original converter retained for one-time migration.
import re
import xml.etree.ElementTree as ET

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
AAAPT_NS = "{http://schemas.android.com/aapt}"

COLOR_KEY_TO_SVG = {
    "fill": "fill",
    "stroke": "stroke",
}

FILL_TYPE_MAP = {
    "evenOdd": "evenodd",
    "nonZero": "nonzero",
}

LINE_CAP_MAP = {
    "butt": "butt",
    "round": "round",
    "square": "square",
}

LINE_JOIN_MAP = {
    "bevel": "bevel",
    "miter": "miter",
    "round": "round",
}

def parse_icon_res_map(text: str) -> tuple[dict[int, str], set[int]]:
    icon_map: dict[int, str] = {}
    single_color = set()

    for match in re.finditer(r"put\((-?\d+),\s*R\.drawable\.(\w+)\)", text):
        index = int(match.group(1))
        icon_map[index] = match.group(2)

    array_match = re.search(r"iconResIds\s*=\s*intArrayOf\((.*?)\)", text, flags=re.S)
    if array_match:
        array_body = array_match.group(1)
        indexed_matches = list(re.finditer(r"/\*\s*(-?\d+)\s*\*/\s*R\.drawable\.(\w+)", array_body))
        if indexed_matches:
            for match in indexed_matches:
                icon_map[int(match.group(1))] = match.group(2)
        else:
            for index, icon_name in enumerate(re.findall(r"R\.drawable\.(\w+)", array_body)):
                icon_map[index] = icon_name

    set_match = re.search(
        r"(?:SINGLE_COLOR_ICON_SET|singleColorIconIndexes)\s*=\s*setOf\((.*?)\)",
        text,
        flags=re.S,
    )
    if set_match:
        set_body = set_match.group(1).replace("PLACEHOLDER_INDEX", "-1")
        for number in re.findall(r"-?\d+", set_body):
            single_color.add(int(number))

    return icon_map, single_color


def convert_vector_xml_to_svg(xml_text: str, icon_name: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    if not root.tag.endswith("vector"):
        return None

    width = parse_dimension(root.attrib.get(f"{ANDROID_NS}width"), "24")
    height = parse_dimension(root.attrib.get(f"{ANDROID_NS}height"), "24")
    viewport_width = parse_dimension(root.attrib.get(f"{ANDROID_NS}viewportWidth"), width)
    viewport_height = parse_dimension(root.attrib.get(f"{ANDROID_NS}viewportHeight"), height)

    defs: list[str] = []
    body = render_children(root, defs, icon_name)
    defs_block = f"<defs>{''.join(defs)}</defs>" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {viewport_width} {viewport_height}" fill="none">'
        f"{defs_block}{body}</svg>"
    )


def render_children(node: ET.Element, defs: list[str], icon_name: str) -> str:
    parts: list[str] = []
    for child in list(node):
        rendered = render_node(child, defs, icon_name)
        if rendered:
            parts.append(rendered)
    return "".join(parts)


def render_node(node: ET.Element, defs: list[str], icon_name: str) -> str:
    tag = strip_namespace(node.tag)
    if tag == "group":
        return render_group(node, defs, icon_name)
    if tag == "path":
        return render_path(node, defs, icon_name)
    if tag == "clip-path":
        clip_id, clip_path = build_clip_path(node, icon_name, defs)
        return f'<g clip-path="url(#{clip_id})"></g>' if clip_path else ""
    return ""


def render_group(node: ET.Element, defs: list[str], icon_name: str) -> str:
    transform = build_group_transform(node.attrib)
    clip_paths: list[str] = []
    children_parts: list[str] = []

    for child in list(node):
        child_tag = strip_namespace(child.tag)
        if child_tag == "clip-path":
            clip_id, clip_path = build_clip_path(child, icon_name, defs)
            if clip_path:
                clip_paths.append(clip_id)
            continue
        rendered = render_node(child, defs, icon_name)
        if rendered:
            children_parts.append(rendered)

    content = "".join(children_parts)
    if not content:
        return ""

    attrs = []
    if transform:
        attrs.append(f' transform="{transform}"')

    for clip_id in clip_paths:
        content = f'<g clip-path="url(#{clip_id})">{content}</g>'

    return f"<g{''.join(attrs)}>{content}</g>"


def build_group_transform(attrs: dict[str, str]) -> str:
    rotation = parse_float(attrs.get(f"{ANDROID_NS}rotation"), 0.0)
    pivot_x = parse_float(attrs.get(f"{ANDROID_NS}pivotX"), 0.0)
    pivot_y = parse_float(attrs.get(f"{ANDROID_NS}pivotY"), 0.0)
    scale_x = parse_float(attrs.get(f"{ANDROID_NS}scaleX"), 1.0)
    scale_y = parse_float(attrs.get(f"{ANDROID_NS}scaleY"), 1.0)
    translate_x = parse_float(attrs.get(f"{ANDROID_NS}translateX"), 0.0)
    translate_y = parse_float(attrs.get(f"{ANDROID_NS}translateY"), 0.0)

    transforms: list[str] = []
    if translate_x or translate_y:
        transforms.append(f"translate({format_number(translate_x)} {format_number(translate_y)})")
    if rotation:
        transforms.append(
            f"translate({format_number(pivot_x)} {format_number(pivot_y)}) "
            f"rotate({format_number(rotation)}) "
            f"translate({format_number(-pivot_x)} {format_number(-pivot_y)})"
        )
    if scale_x != 1.0 or scale_y != 1.0:
        transforms.append(
            f"translate({format_number(pivot_x)} {format_number(pivot_y)}) "
            f"scale({format_number(scale_x)} {format_number(scale_y)}) "
            f"translate({format_number(-pivot_x)} {format_number(-pivot_y)})"
        )

    return " ".join(transforms)


def build_clip_path(node: ET.Element, icon_name: str, defs: list[str]) -> tuple[str, str]:
    path_data = node.attrib.get(f"{ANDROID_NS}pathData")
    if not path_data:
        return "", ""

    clip_id = f"{icon_name}-clip-{len(defs)}"
    defs.append(f'<clipPath id="{clip_id}"><path d="{escape_xml(path_data)}" /></clipPath>')
    return clip_id, path_data


def render_path(node: ET.Element, defs: list[str], icon_name: str) -> str:
    path_data = node.attrib.get(f"{ANDROID_NS}pathData")
    if not path_data:
        return ""

    attrs = [f'd="{escape_xml(path_data)}"']
    alpha_multiplier = 1.0

    fill_attr = None
    stroke_attr = None
    gradient_fill = extract_gradient_fill(node, defs, icon_name)

    if gradient_fill:
        fill_attr = f'fill="url(#{gradient_fill})"'
    else:
        fill_attr, fill_alpha = build_color_attribute(node.attrib.get(f"{ANDROID_NS}fillColor"), "fill")
        alpha_multiplier *= fill_alpha

    stroke_attr, stroke_alpha = build_color_attribute(node.attrib.get(f"{ANDROID_NS}strokeColor"), "stroke")

    if fill_attr:
        attrs.append(fill_attr)
    else:
        attrs.append('fill="none"')

    if stroke_attr:
        attrs.append(stroke_attr)
        alpha_multiplier *= stroke_alpha
        stroke_width = node.attrib.get(f"{ANDROID_NS}strokeWidth")
        if stroke_width:
            attrs.append(f'stroke-width="{format_number(parse_float(stroke_width, 0.0))}"')
        stroke_cap = LINE_CAP_MAP.get(node.attrib.get(f"{ANDROID_NS}strokeLineCap", ""))
        if stroke_cap:
            attrs.append(f'stroke-linecap="{stroke_cap}"')
        stroke_join = LINE_JOIN_MAP.get(node.attrib.get(f"{ANDROID_NS}strokeLineJoin", ""))
        if stroke_join:
            attrs.append(f'stroke-linejoin="{stroke_join}"')
        stroke_miter = node.attrib.get(f"{ANDROID_NS}strokeMiterLimit")
        if stroke_miter:
            attrs.append(f'stroke-miterlimit="{format_number(parse_float(stroke_miter, 0.0))}"')

    path_alpha = parse_float(node.attrib.get(f"{ANDROID_NS}fillAlpha"), 1.0)
    if path_alpha != 1.0:
        alpha_multiplier *= path_alpha

    stroke_alpha_attr = node.attrib.get(f"{ANDROID_NS}strokeAlpha")
    if stroke_attr and stroke_alpha_attr:
        attrs.append(f'stroke-opacity="{format_number(parse_float(stroke_alpha_attr, 1.0))}"')

    if alpha_multiplier != 1.0:
        attrs.append(f'fill-opacity="{format_number(alpha_multiplier)}"')

    fill_type = FILL_TYPE_MAP.get(node.attrib.get(f"{ANDROID_NS}fillType", ""))
    if fill_type:
        attrs.append(f'fill-rule="{fill_type}"')

    return f"<path {' '.join(attrs)} />"


def extract_gradient_fill(node: ET.Element, defs: list[str], icon_name: str) -> str | None:
    for child in list(node):
        if strip_namespace(child.tag) != "attr":
            continue
        if child.attrib.get("name") != "android:fillColor":
            continue

        gradient = next(iter(list(child)), None)
        if gradient is None:
            return None

        gradient_id = f"{icon_name}-gradient-{len(defs)}"
        defs.append(render_gradient(gradient, gradient_id))
        return gradient_id

    return None


def render_gradient(node: ET.Element, gradient_id: str) -> str:
    gradient_type = node.attrib.get(f"{ANDROID_NS}type", "linear")
    if gradient_type == "radial":
        center_x = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}centerX"), 0.0))
        center_y = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}centerY"), 0.0))
        radius = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}gradientRadius"), 0.0))
        attrs = (
            f'id="{gradient_id}" cx="{center_x}" cy="{center_y}" r="{radius}" '
            'gradientUnits="userSpaceOnUse"'
        )
        tag = "radialGradient"
    else:
        start_x = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}startX"), 0.0))
        start_y = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}startY"), 0.0))
        end_x = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}endX"), 0.0))
        end_y = format_number(parse_float(node.attrib.get(f"{ANDROID_NS}endY"), 0.0))
        attrs = (
            f'id="{gradient_id}" x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" '
            'gradientUnits="userSpaceOnUse"'
        )
        tag = "linearGradient"

    items = []
    for item in list(node):
        if strip_namespace(item.tag) != "item":
            continue
        offset = format_number(parse_float(item.attrib.get(f"{ANDROID_NS}offset"), 0.0))
        color_value = item.attrib.get(f"{ANDROID_NS}color")
        color, opacity = parse_color(color_value)
        item_attrs = [f'offset="{offset}"']
        if color:
            item_attrs.append(f'stop-color="{color}"')
        if opacity is not None and opacity != 1.0:
            item_attrs.append(f'stop-opacity="{format_number(opacity)}"')
        items.append(f"<stop {' '.join(item_attrs)} />")

    return f"<{tag} {attrs}>{''.join(items)}</{tag}>"


def build_color_attribute(color_value: str | None, svg_attr: str) -> tuple[str | None, float]:
    color, opacity = parse_color(color_value)
    if not color:
        return None, 1.0
    attr = f'{svg_attr}="{color}"'
    return attr, opacity if opacity is not None else 1.0


def parse_color(color_value: str | None) -> tuple[str | None, float | None]:
    if not color_value:
        return None, None

    value = color_value.strip()
    if value.lower() == "@android:color/transparent":
        return "none", 1.0

    if not value.startswith("#"):
        return None, None

    hex_value = value[1:]
    if len(hex_value) == 8:
        alpha = int(hex_value[0:2], 16) / 255
        return f"#{hex_value[2:]}", alpha
    if len(hex_value) == 6:
        return value, 1.0
    if len(hex_value) == 4:
        alpha = int(hex_value[0] * 2, 16) / 255
        rgb = "".join(character * 2 for character in hex_value[1:])
        return f"#{rgb}", alpha
    if len(hex_value) == 3:
        rgb = "".join(character * 2 for character in hex_value)
        return f"#{rgb}", 1.0

    return value, 1.0


def parse_dimension(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    match = re.match(r"(-?\d+(?:\.\d+)?)", value)
    return match.group(1) if match else fallback


def parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value).replace("dp", ""))
    except ValueError:
        return default


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
