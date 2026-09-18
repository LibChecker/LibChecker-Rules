"""Bounded standalone Android VectorDrawable source validation, no SVG inversion."""
import re
import xml.etree.ElementTree as ET
from vector_import import ANDROID_NS, AAAPT_NS, convert_vector_xml_to_svg

ATTRIBUTES = {
    'vector': {'width','height','viewportWidth','viewportHeight','tint'},
    'group': {'name','rotation','pivotX','pivotY','scaleX','scaleY','translateX','translateY'},
    'path': {'name','pathData','fillColor','fillAlpha','fillType','strokeColor','strokeAlpha','strokeWidth','strokeLineCap','strokeLineJoin','strokeMiterLimit'},
    'clip-path': {'name','pathData','fillType'},
    'gradient': {'startColor','centerColor','endColor','startX','startY','endX','endY','centerX','centerY','type','gradientRadius'},
    'item': {'color','offset'},
}
CHILDREN = {'vector':{'group','path','clip-path'},'group':{'group','path','clip-path'},'path':{AAAPT_NS+'attr'},'clip-path':set(),AAAPT_NS+'attr':{'gradient'},'gradient':{'item'},'item':set()}


def validate_vector(raw, icon_id):
    if len(raw)>256*1024:raise ValueError('Vector exceeds 256 KiB')
    text=raw.decode('utf-8')
    # Existing originals contain XML declarations. Permit only that declaration.
    cleaned=re.sub(r'^\s*<\?xml\s+[^?]*\?>','',text,count=1)
    cleaned=re.sub(r'<!--.*?-->','',cleaned,flags=re.S)
    if '<!' in cleaned or '<?' in cleaned:raise ValueError('Vector declarations/entities forbidden')
    root=ET.fromstring(text)
    if root.tag!='vector':raise ValueError('Expected Android vector root')
    count=0
    def visit(node,depth):
        nonlocal count
        count+=1
        if depth>32 or count>4096:raise ValueError('Vector structure limit')
        if node.tag not in CHILDREN:raise ValueError(f'Unsupported vector element {node.tag}')
        if (node.text or '').strip() or (node.tail or '').strip():raise ValueError('Vector text forbidden')
        for key,value in node.attrib.items():
            if node.tag==AAAPT_NS+'attr':
                if key!='name' or value not in ('android:fillColor','android:strokeColor'):raise ValueError('Unsupported aapt attribute')
            elif not key.startswith(ANDROID_NS) or key[len(ANDROID_NS):] not in ATTRIBUTES[node.tag]:
                raise ValueError(f'Unsupported vector attribute {key}')
            if '@' in value or '?' in value:
                if not (node.tag=='vector' and key==ANDROID_NS+'tint' and value=='?android:attr/colorControlNormal'):
                    raise ValueError('Vector must not depend on external resources')
            if '://' in value:raise ValueError('External vector value')
        for child in node:
            if child.tag not in CHILDREN[node.tag]:raise ValueError('Invalid vector nesting')
            visit(child,depth+1)
    visit(root,1)
    for field in ('width','height','viewportWidth','viewportHeight'):
        value=root.get(ANDROID_NS+field,'')
        if not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:dp)?',value) or float(value.removesuffix('dp'))<=0:
            raise ValueError(f'Invalid vector {field}')
    svg=convert_vector_xml_to_svg(text,icon_id)
    if not svg:raise ValueError('Cannot derive web SVG')
    return (svg+'\n').encode()
