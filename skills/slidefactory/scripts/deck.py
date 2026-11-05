#!/usr/bin/env python3
"""Checked, surgical edits of standalone SlideFactory HTML; Python stdlib only.

Source spans are character offsets into a strictly decoded UTF-8 byte string.
No HTML is reserialized. Re-encoding unchanged spans reproduces their bytes,
including CRLF, comments, SVG, assets, custom CSS, and raw script contents.
"""

import argparse
import base64
from dataclasses import dataclass, field
import html
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tempfile
from urllib.parse import unquote, unquote_to_bytes
import uuid


class DeckError(ValueError):
    """Invalid or unsupported authored source; no destination has been written."""


VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
TOKENS = ("background", "text", "muted", "accent", "accent2", "surface", "border")
COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
DATA_URI = re.compile(r"\bdata:[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+(?:;[^,\r\n]*)?,", re.I)
PIXEL = re.compile(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))px\Z", re.I)


@dataclass
class Node:
    tag: str
    attrs: dict
    start: int
    open_end: int
    parent: "Node | None" = None
    close_start: int = 0
    end: int = 0
    children: list = field(default_factory=list)

    def inside(self, ancestor):
        current = self.parent
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False


class SourceParser(HTMLParser):
    """Conservative explicit-tag HTML subset, with browser-style raw scripts."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0]
        self.offsets.extend(match.end() for match in re.finditer("\n", source))
        self.nodes = []
        self.stack = []
        self.root_text = []
        self.feed(source)
        self.close()
        if self.stack:
            raise DeckError(f"Unclosed <{self.stack[-1].tag}>; use explicit closing tags.")

    def position(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def opening(self, tag, attrs, self_closing):
        values = {}
        for key, value in attrs:
            if key in values:
                raise DeckError(f"Ambiguous duplicate attribute {key!r} on <{tag}>.")
            values[key] = value
        start = self.position()
        node = Node(tag, values, start, start + len(self.get_starttag_text()), self.stack[-1] if self.stack else None)
        self.nodes.append(node)
        if node.parent:
            node.parent.children.append(node)
        if self_closing or tag in VOID:
            node.close_start = node.end = node.open_end
        else:
            self.stack.append(node)

    def handle_starttag(self, tag, attrs):
        self.opening(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        # HTML ignores XML slash syntax for non-void HTML elements. Only SVG
        # foreign content permits it; accepting <section/> would invent spans.
        in_foreign = any(node.tag in {"svg", "math"} for node in self.stack)
        if tag not in VOID and not in_foreign and tag not in {"svg", "math"}:
            raise DeckError(f"Self-closing <{tag}/> is unsupported HTML; close it explicitly.")
        self.opening(tag, attrs, True)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1].tag != tag:
            raise DeckError(f"Mismatched closing </{tag}>; source is not safely editable.")
        node = self.stack.pop()
        node.close_start = self.position()
        ending = self.source.find(">", node.close_start)
        if ending < 0:
            raise DeckError(f"Incomplete closing </{tag}>.")
        node.end = ending + 1

    def handle_data(self, data):
        if not self.stack and data.strip("\ufeff \t\r\n"):
            self.root_text.append(data)

    def handle_entityref(self, name):
        if not self.stack:
            self.root_text.append("&" + name + ";")

    def handle_charref(self, name):
        if not self.stack:
            self.root_text.append("&#" + name + ";")

    def unknown_decl(self, data):
        # CDATA in SVG is authored raw content. Other declarations are rejected.
        if not any(node.tag in {"svg", "math"} for node in self.stack):
            raise DeckError("Unsupported declaration outside SVG/MathML.")


def read_source(path):
    try:
        return Path(path).read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise DeckError("Source must be literal UTF-8 HTML.") from error


def json_value(raw, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DeckError(f"{label}: duplicate JSON key {key!r}.")
            result[key] = value
        return result

    def constant(value):
        raise DeckError(f"{label}: non-finite JSON number {value}.")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as error:
        raise DeckError(f"{label}: invalid JSON at line {error.lineno}, column {error.colno}.") from error
    except ValueError as error:
        raise DeckError(f"{label}: invalid JSON value ({error}).") from error


def json_source(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def identifier(value, label):
    if not isinstance(value, str) or not value or value.strip() != value or re.search(r"\s", value):
        raise DeckError(f"{label} needs a nonempty ID without whitespace.")


def number(value, label, positive=False):
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise DeckError(f"{label} must be a finite number.")
    if positive and value <= 0:
        raise DeckError(f"{label} must be positive.")
    return value


def geometry(node):
    properties = {}
    for declaration in (node.attrs.get("style") or "").split(";"):
        if ":" in declaration:
            key, value = declaration.split(":", 1)
            properties[key.strip().lower()] = value.strip()
    result = {}
    for key in ("left", "top", "width", "height"):
        match = PIXEL.fullmatch(properties.get(key, ""))
        if match:
            result[key] = float(match[1])
    if "transform" in properties:
        result["transform"] = properties["transform"]
    return result


def layout_offsets(node):
    """Report authored offsets only; never pretend measured flow bounds are CSS."""
    properties = {}
    for declaration in (node.attrs.get("style") or "").split(";"):
        if ":" in declaration:
            key, value = declaration.split(":", 1)
            properties[key.strip().lower()] = value.strip()
    return {key: value for key, value in properties.items() if key in {"translate", "left", "top", "position", "transform"}}


def exif_orientation(segment):
    """Read TIFF IFD0 orientation without decoding or altering JPEG pixels."""
    if not segment.startswith(b"Exif\x00\x00"):
        return 1
    tiff = segment[6:]
    if len(tiff) < 8 or tiff[:2] not in {b"II", b"MM"}:
        return 1
    endian = "little" if tiff[:2] == b"II" else "big"
    if int.from_bytes(tiff[2:4], endian) != 42:
        return 1
    offset = int.from_bytes(tiff[4:8], endian)
    if offset + 2 > len(tiff):
        return 1
    count = int.from_bytes(tiff[offset:offset + 2], endian)
    for index in range(count):
        start = offset + 2 + index * 12
        entry = tiff[start:start + 12]
        if len(entry) != 12:
            break
        if int.from_bytes(entry[:2], endian) == 0x0112 and int.from_bytes(entry[2:4], endian) == 3 and int.from_bytes(entry[4:8], endian) == 1:
            value = int.from_bytes(entry[8:10], endian)
            return value if 1 <= value <= 8 else 1
    return 1


def image_data(src):
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|svg\+xml))((?:;[^,]*)?),(.*)", src or "", re.I | re.S)
    if not match:
        raise DeckError("Images must embed a PNG/JPEG/WebP or trusted SVG data URL; external images are unsupported.")
    mime, parameters, payload = match.groups()
    try:
        data = base64.b64decode(payload, validate=True) if ";base64" in parameters.lower() else unquote_to_bytes(payload)
    except (ValueError, base64.binascii.Error) as error:
        raise DeckError("Invalid embedded image encoding.") from error
    if not data:
        raise DeckError("Embedded image is empty.")
    mime = mime.lower()
    dimensions = None
    if mime == "image/png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise DeckError("Embedded PNG has no valid image header.")
        dimensions = struct.unpack(">II", data[16:24])
    elif mime == "image/jpeg":
        if not data.startswith(b"\xff\xd8"):
            raise DeckError("Embedded JPEG has no valid image header.")
        offset, orientation = 2, 1
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                break
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker == 0xDA:  # Start of compressed scan; no more metadata.
                break
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and length >= 7:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                dimensions = (width, height)
            if marker == 0xE1:
                orientation = exif_orientation(data[offset + 2:offset + length])
            offset += length
        if dimensions is None:
            raise DeckError("Embedded JPEG is missing its dimensions.")
        if orientation in {5, 6, 7, 8}:
            dimensions = dimensions[::-1]
    elif mime == "image/webp":
        if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise DeckError("Embedded WebP has no valid image header.")
        kind = data[12:16]
        if kind == b"VP8X" and len(data) >= 30:
            dimensions = (1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little"))
        elif kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            dimensions = ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        elif kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            dimensions = (int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF)
        if dimensions is None:
            raise DeckError("Embedded WebP is missing its dimensions.")
    else:
        # Template SVG originals are trusted authored assets. They are never
        # inserted as live markup, executed, or included in inspect output.
        if not re.search(rb"<svg(?:\s|>)", data, re.I):
            raise DeckError("Embedded SVG has no SVG root.")
    if dimensions and min(dimensions) <= 0:
        raise DeckError("Embedded image dimensions must be positive.")
    return {"mime": mime, "bytes": len(data), "dimensions": dimensions}


class NotesFormatParser(HTMLParser):
    """Strict persisted notes grammar; never repairs input while validating."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack = [("root", [])]
        self.canonical = []
        self.feed(source)
        self.close()
        if len(self.stack) != 1:
            raise DeckError("Unclosed note markup.")
        self.text = "".join(self.stack[0][1])
        if self.text.endswith("\n"):
            self.text = self.text[:-1]

    def handle_starttag(self, tag, attrs):
        parent, parts = self.stack[-1]
        inline = {"br", "strong", "em", "span"}
        allowed = {"p", "ul", "ol"} if parent == "root" else {"li"} if parent in {"ul", "ol"} else inline | {"ul", "ol"} if parent == "li" else inline
        if tag not in allowed:
            raise DeckError("Invalid note markup nesting.")
        suffix = ""
        if tag == "span":
            if len(attrs) != 1 or attrs[0][0] != "style" or not re.fullmatch(r"font-size:(?:\d+(?:\.\d+)?|\.\d+)pt", attrs[0][1] or ""):
                raise DeckError("Invalid note font size.")
            size = float(attrs[0][1][10:-2])
            if not 8 <= size <= 72:
                raise DeckError("Note font size must be 8–72pt.")
            suffix = f' style="{attrs[0][1]}"'
        elif attrs:
            raise DeckError("Note attributes are not supported.")
        self.canonical.append(f"<{tag}{suffix}>")
        if parent == "li" and tag in {"ul", "ol"} and parts and not "".join(parts).endswith("\n"):
            parts.append("\n")
        if tag == "br":
            parts.append("\n")
        else:
            self.stack.append((tag, []))

    def handle_endtag(self, tag):
        if len(self.stack) < 2 or self.stack[-1][0] != tag:
            raise DeckError("Invalid note closing tag.")
        _, parts = self.stack.pop()
        text = "".join(parts)
        if tag == "p" or tag == "li" and not text.endswith("\n"):
            text += "\n"
        self.stack[-1][1].append(text)
        self.canonical.append(f"</{tag}>")

    def handle_data(self, text):
        if self.stack[-1][0] not in {"p", "li", "strong", "em", "span"}:
            raise DeckError("Note text must be inside a paragraph or list item.")
        if "\x00" in text:
            raise DeckError("NUL is not representable in note HTML.")
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        self.stack[-1][1].append(text)
        self.canonical.append(html.escape(text, quote=False))

    def handle_comment(self, _):
        raise DeckError("Comments are not note content.")

    def handle_decl(self, _):
        raise DeckError("Declarations are not note content.")

    def handle_pi(self, _):
        raise DeckError("Processing instructions are not note content.")


def validate_notes_format(value):
    if not isinstance(value, dict) or set(value) != {"version", "text", "html"} or type(value["version"]) is not int or value["version"] != 1:
        raise DeckError("Invalid notesFormat entry.")
    for key, maximum in (("text", 200000), ("html", 800000)):
        if not isinstance(value[key], str) or len(value[key].encode("utf-16-le", errors="surrogatepass")) // 2 > maximum:
            raise DeckError("Invalid or oversized formatted note.")
    parsed = NotesFormatParser(value["html"])
    if "".join(parsed.canonical) != value["html"] or parsed.text != value["text"]:
        raise DeckError("Noncanonical note markup or mismatched plain text.")


class Deck:
    def __init__(self, source):
        self.source = source
        self.parser = SourceParser(source)
        self.nodes = self.parser.nodes
        roots = [node for node in self.nodes if node.parent is None]
        if self.parser.root_text or len(roots) != 1 or roots[0].tag != "html":
            raise DeckError("Unsupported file: expected one complete standalone SlideFactory HTML document.")
        self.root = roots[0]
        heads = [node for node in self.root.children if node.tag == "head"]
        bodies = [node for node in self.root.children if node.tag == "body"]
        if len(heads) != 1 or len(bodies) != 1 or len(self.root.children) != 2:
            raise DeckError("Standalone HTML requires one explicit <head> and <body>.")
        self.head, self.body = heads[0], bodies[0]
        self.main = self.unique("sf-deck", "main")
        if not self.main.inside(self.body):
            raise DeckError("#sf-deck must be inside <body>.")
        self.document_node = self.unique("sf-document", "script")
        self.scheme_node = self.unique("sf-color-schemes", "script")
        self.theme_node = self.unique("sf-theme-tokens", "style")
        self.meta = self.json_node(self.document_node)
        self.schemes = self.json_node(self.scheme_node)
        self.slides, self.objects = {}, {}
        self.validate_structure()
        self.validate_metadata()
        self.validate_resources()

    def unique(self, identity, tag):
        matches = [node for node in self.nodes if node.attrs.get("id") == identity]
        if len(matches) != 1 or matches[0].tag != tag:
            raise DeckError(f"Unsupported file: need exactly one <{tag} id=\"{identity}\">.")
        return matches[0]

    def inner(self, node):
        return self.source[node.open_end:node.close_start]

    def outer(self, node):
        return self.source[node.start:node.end]

    def json_node(self, node):
        if node.attrs.get("type") != "application/json":
            raise DeckError(f"#{node.attrs['id']} must use type=application/json.")
        value = json_value(self.inner(node), node.attrs["id"])
        if not isinstance(value, dict):
            raise DeckError(f"#{node.attrs['id']} must contain a JSON object.")
        return value

    def validate_structure(self):
        if not self.main.children:
            raise DeckError("#sf-deck must contain at least one slide.")
        for slide in self.main.children:
            identity = slide.attrs.get("data-sf-slide")
            identifier(identity, "Slide")
            if slide.tag != "section" or "sf-slide" not in (slide.attrs.get("class") or "").split():
                raise DeckError("#sf-deck children must be section.sf-slide elements.")
            if identity in self.slides:
                raise DeckError(f"Duplicate slide ID {identity!r}.")
            self.slides[identity] = slide
            if "data-sf-duration" in slide.attrs:
                raw = slide.attrs["data-sf-duration"] or ""
                if not re.fullmatch(r"\d+(?:\.\d+)?", raw):
                    raise DeckError("Slide duration must be finite nonnegative seconds.")
                number(float(raw), "Slide duration", True)
            if "data-sf-part" in slide.attrs:
                label = slide.attrs["data-sf-part"] or ""
                if not label.strip() or len(label) > 80:
                    raise DeckError("data-sf-part needs a nonempty label of at most 80 characters.")
            if "data-sf-part-duration" in slide.attrs:
                raw = slide.attrs["data-sf-part-duration"] or ""
                if "data-sf-part" not in slide.attrs or not re.fullmatch(r"\d+(?:\.\d+)?", raw) or float(raw) <= 0:
                    raise DeckError("data-sf-part-duration needs positive seconds on a slide with data-sf-part.")
        budgets = {}
        for slide in self.slides.values():
            if "data-sf-part-duration" in slide.attrs:
                label = slide.attrs["data-sf-part"].strip()
                if budgets.setdefault(label, slide.attrs["data-sf-part-duration"]) != slide.attrs["data-sf-part-duration"]:
                    raise DeckError(f"Part {label!r} declares conflicting data-sf-part-duration values.")
        for node in self.nodes:
            if "data-sf-link" in node.attrs and "data-sf-id" not in node.attrs:
                raise DeckError("data-sf-link marks an editable slide-link object and needs data-sf-id.")
            if "data-sf-slide" in node.attrs and node not in self.main.children:
                raise DeckError("Slides must be direct children of #sf-deck.")
            marked = "data-sf-id" in node.attrs or "data-sf-kind" in node.attrs
            if "data-sf-layout" in node.attrs and (not marked or node.attrs.get("data-sf-layout") not in {"flow", "inline"} or node.attrs.get("data-sf-kind") not in {"text", "box"}):
                raise DeckError("data-sf-layout must be flow|inline on a text or box object.")
            if not marked:
                continue
            identity, kind = node.attrs.get("data-sf-id"), node.attrs.get("data-sf-kind")
            identifier(identity, "Editable object")
            if kind not in {"text", "box", "image"}:
                raise DeckError(f"Object {identity!r} needs data-sf-kind=text|box|image.")
            if identity in self.objects or identity in self.slides:
                raise DeckError(f"Duplicate slide/editable object ID {identity!r}; SF identities share one namespace.")
            if not any(node.inside(slide) for slide in self.slides.values()):
                raise DeckError(f"Editable object {identity!r} must be inside a slide.")
            if kind == "text" and (node.tag in VOID or node.tag in {"script", "style", "iframe"}):
                raise DeckError(f"Text object {identity!r} must be an ordinary content element.")
            if "data-sf-link" in node.attrs and (kind != "text" or node.tag != "a" or not re.fullmatch(r"#[^#\s]+", node.attrs.get("href") or "")):
                raise DeckError(f"Slide link {identity!r} must be a text-kind <a> with href=\"#<slide ID>\".")
            self.objects[identity] = node
            if kind == "image":
                self.validate_image(node)

    def validate_image(self, node):
        images = [image for image in self.nodes if image.tag == "img" and image.inside(node)]
        if len(images) != 1 or images[0].parent is not node:
            raise DeckError(f"Image object {node.attrs['data-sf-id']!r} needs one direct original <img>.")
        image = images[0]
        try:
            width, height = float(image.attrs.get("width", "")), float(image.attrs.get("height", ""))
        except (ValueError, TypeError) as error:
            raise DeckError("Image original requires explicit positive width/height dimensions.") from error
        number(width, "Image original width", True)
        number(height, "Image original height", True)
        original = image_data(image.attrs.get("src"))
        if original["dimensions"] and (width, height) != original["dimensions"]:
            raise DeckError("Image width/height must match embedded original dimensions.")
        crop = json_value(node.attrs.get("data-sf-crop") or "", "data-sf-crop")
        if not isinstance(crop, dict) or not all(key in crop for key in ("x", "y", "w", "h")):
            raise DeckError("data-sf-crop requires {x,y,w,h}.")
        for key in ("x", "y", "w", "h"):
            value = number(crop[key], "Crop " + key, key in {"w", "h"})
            if value < 0 or value > 1:
                raise DeckError("Crop coordinates must be normalized within [0,1].")
        if crop["x"] + crop["w"] > 1 + 1e-9 or crop["y"] + crop["h"] > 1 + 1e-9:
            raise DeckError("Crop must be contained within the original image.")
        frame = geometry(node)
        for key in ("left", "top", "width", "height"):
            if key not in frame:
                raise DeckError("Image frame requires finite inline left/top/width/height CSS pixels.")
            number(frame[key], "Image frame " + key, key in {"width", "height"})
        if not math.isclose((crop["w"] * width) / (crop["h"] * height), frame["width"] / frame["height"], rel_tol=1e-5, abs_tol=1e-7):
            raise DeckError("Crop aspect must match the image frame aspect.")

    def validate_metadata(self):
        meta = self.meta
        if type(meta.get("schemaVersion")) is not int or meta["schemaVersion"] != 1:
            raise DeckError("Unsupported schemaVersion; this helper supports SlideFactory schema 1.")
        for key in ("deckId", "revision", "templateId"):
            identifier(meta.get(key), key)
        for key in ("title", "templateVersion", "colorScheme"):
            if not isinstance(meta.get(key), str):
                raise DeckError(f"Metadata {key} must be a string.")
        if "postitsVisible" in meta and not isinstance(meta["postitsVisible"], bool):
            raise DeckError("postitsVisible must be a boolean.")
        if "backgroundColor" in meta and (not isinstance(meta["backgroundColor"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", meta["backgroundColor"])):
            raise DeckError("backgroundColor must be a six-digit hex color.")
        for key, expected in (("pageWidth", 1600), ("pageHeight", 900)):
            if isinstance(meta.get(key), bool) or meta.get(key) != expected:
                raise DeckError(f"Metadata {key} must be {expected}.")
        for key in ("notes", "guidance"):
            if not isinstance(meta.get(key), dict):
                raise DeckError(f"Metadata {key} must be an object keyed by slide ID.")
            if set(meta[key]) - set(self.slides):
                raise DeckError(f"Metadata {key} refers to a missing slide.")
        if any(not isinstance(value, str) for value in meta["notes"].values()):
            raise DeckError("Notes must be plain strings.")
        if "notesFormat" in meta:
            formats = meta["notesFormat"]
            if not isinstance(formats, dict) or set(formats) - set(self.slides):
                raise DeckError("notesFormat must be keyed by existing slide ID.")
            for value in formats.values():
                validate_notes_format(value)
        if "notesProvenance" in meta:
            provenance = meta["notesProvenance"]
            if not isinstance(provenance, dict) or set(provenance) - set(self.slides):
                raise DeckError("notesProvenance must be keyed by existing slide ID.")
            if any(not isinstance(value, dict) or not isinstance(value.get("html"), str) or not isinstance(value.get("text"), str) for value in provenance.values()):
                raise DeckError("notesProvenance entries require html and text strings.")
        for value in meta["guidance"].values():
            if not isinstance(value, dict) or not isinstance(value.get("text"), str) or not isinstance(value.get("status"), str) or value["status"] not in {"open", "addressed"}:
                raise DeckError("Guidance requires text and status=open|addressed.")
        if not self.schemes or meta["colorScheme"] not in self.schemes:
            raise DeckError("Metadata colorScheme must identify a declared scheme.")
        for key, scheme in self.schemes.items():
            identifier(key, "Color scheme")
            if not isinstance(scheme, dict) or not isinstance(scheme.get("label"), str) or not isinstance(scheme.get("tokens"), dict):
                raise DeckError("Each color scheme requires label and tokens.")
            for token in TOKENS:
                value = scheme["tokens"].get(token)
                if not isinstance(value, str) or not COLOR.fullmatch(value):
                    raise DeckError(f"Color token {token!r} must be #RGB, #RRGGBB or #RRGGBBAA.")
        derived = dict(re.findall(r"--sf-([a-zA-Z0-9-]+)\s*:\s*(#[0-9a-fA-F]+)\s*(?:;|})", self.inner(self.theme_node)))
        for token in TOKENS:
            if not COLOR.fullmatch(derived.get(token, "")):
                raise DeckError("#sf-theme-tokens must declare seven portable hex color variables.")
        # Metadata selects a palette. Runtime derives its colors on every load;
        # a CLI scheme selection need not rewrite any authored/shared CSS.

    def validate_resources(self):
        for node in self.nodes:
            if node.tag == "script" and "src" in node.attrs:
                raise DeckError("Standalone runtime scripts must be inline.")
            if node.tag == "link" and node.attrs.get("href") and not node.attrs["href"].startswith(("data:", "#")):
                raise DeckError("Standalone linked resources must be embedded.")
            if node.tag == "base":
                raise DeckError("Standalone source cannot override the base URL.")
            if node.tag == "img":
                image_data(node.attrs.get("src"))
            if "srcset" in node.attrs:
                raise DeckError("Use one embedded original image, without srcset dependencies.")
            if node.tag in {"image", "use"}:
                reference = node.attrs.get("href", node.attrs.get("xlink:href"))
                if reference and not reference.startswith(("#", "data:")):
                    raise DeckError("SVG assets must be inline references or embedded data URLs.")
                if node.tag == "image" and reference and reference.startswith("data:"):
                    image_data(reference)
            if node.tag != "img" and "src" in node.attrs and not (node.attrs["src"] or "").startswith("data:"):
                raise DeckError("Standalone source resources must be embedded.")
            if node.tag in {"iframe", "object", "embed"}:
                raise DeckError("External embedded documents are unsupported in standalone decks.")
            if node.tag == "style" or "style" in node.attrs:
                css = re.sub(r"/\*.*?\*/", "", self.inner(node) if node.tag == "style" else node.attrs["style"] or "", flags=re.S)
                if re.search(r"@import\b", css, re.I):
                    raise DeckError("Standalone CSS cannot import external stylesheets.")
                for value in re.findall(r"url\(\s*['\"]?(.*?)['\"]?\s*\)", css, re.I | re.S):
                    if not value.startswith(("data:", "#")):
                        raise DeckError("Standalone CSS assets must be embedded data URLs.")

    def links(self, slide):
        """Slide links on one slide: editor link objects and authored #anchors.

        Authored anchors to "#" or to another element id are in-page anchors, not
        slide links. Percent escapes are decoded like the runtime's decodeURIComponent.
        """
        result = []
        element_ids = {node.attrs.get("id") for node in self.nodes if node.attrs.get("id")}
        for node in self.nodes:
            href = node.attrs.get("href") or ""
            if node.tag != "a" or not href.startswith("#") or not node.inside(slide):
                continue
            try:
                if re.search(r"%(?![0-9A-Fa-f]{2})", href):
                    raise ValueError(href)
                target = unquote(href[1:], errors="strict")
            except (UnicodeDecodeError, ValueError):
                target = None
            if "data-sf-link" not in node.attrs and target not in self.slides and (href == "#" or target in element_ids):
                continue
            item = {"id": node.attrs.get("data-sf-id"), "object": "data-sf-link" in node.attrs, "target": target, "text": "".join(TextContent(self.inner(node)).values).strip()}
            item["targetNumber"] = list(self.slides).index(target) + 1 if target in self.slides else None
            result.append(item)
        return result

    def broken_links(self):
        return [{"slideId": identity, "slideNumber": number, **link}
                for number, (identity, slide) in enumerate(self.slides.items(), 1)
                for link in self.links(slide) if link["targetNumber"] is None]

    def select_slide(self, selector, allow_number=False):
        if selector in self.slides:
            return self.slides[selector]
        if allow_number and selector.isdecimal():
            index = int(selector) - 1
            if 0 <= index < len(self.slides):
                return list(self.slides.values())[index]
        raise DeckError(f"Unknown slide {selector!r}; inspect the current IDs first.")

    def metadata_patch(self):
        return (self.document_node.open_end, self.document_node.close_start, json_source(self.meta))


def patched(source, edits):
    ordered = sorted(edits)
    previous = 0
    parts = []
    for start, end, replacement in ordered:
        if start < previous or end < start:
            raise DeckError("Overlapping source edits are unsafe.")
        parts.extend((source[previous:start], replacement))
        previous = end
    parts.append(source[previous:])
    return "".join(parts)


def atomic_write(path, source, mode_from=None, exclusive=False):
    target = Path(path)
    temporary = None
    try:
        mode_path = target if target.exists() else Path(mode_from) if mode_from else None
        mode = stat.S_IMODE(mode_path.stat().st_mode) if mode_path and mode_path.exists() else 0o644
        with tempfile.NamedTemporaryFile(mode="wb", prefix="." + target.name + ".", suffix=".tmp", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        if exclusive:
            os.link(temporary, target)  # Atomic no-clobber publication, including symlinks.
            temporary.unlink()
        else:
            os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parse_fragment(path):
    source = read_source(path)
    parser = SourceParser(source)
    roots = [node for node in parser.nodes if node.parent is None]
    if parser.root_text or len(roots) != 1 or roots[0].tag != "section" or "data-sf-slide" not in roots[0].attrs:
        raise DeckError("Fragment must contain exactly one authored <section data-sf-slide=...>.")
    # Surrounding comments/whitespace are not part of a slide fragment and must
    # not move into a different authored position on replacement/insertion.
    node = roots[0]
    if source[:node.start].strip() or source[node.end:].strip():
        raise DeckError("Fragment may have surrounding whitespace only.")
    return source[node.start:node.end], node.attrs["data-sf-slide"]


class TextContent(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.values, self.hidden = [], 0
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"br", "p", "div"} and self.values:
            self.values.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.values.append(data)


def redacted(value):
    if isinstance(value, dict):
        return {key: redacted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redacted(item) for item in value]
    if isinstance(value, str):
        # Unencoded SVG data URLs may contain whitespace/quotes. Redact the
        # whole value rather than leaving asset bytes after the first space.
        return "[embedded asset omitted]" if DATA_URI.search(value) else value
    return value


def inspection(deck, selector):
    def slide_info(slide):
        identity = slide.attrs["data-sf-slide"]
        objects = []
        for node in deck.objects.values():
            if not node.inside(slide):
                continue
            item = {"id": node.attrs["data-sf-id"], "kind": node.attrs["data-sf-kind"], "tag": node.tag, "geometry": geometry(node)}
            if "data-sf-shape" in node.attrs:
                item["shape"] = node.attrs["data-sf-shape"]
            if "data-sf-postit" in node.attrs:
                item["postit"] = True
            if "data-sf-link" in node.attrs:
                item["link"] = unquote(node.attrs["href"][1:])
            if "data-sf-layout" in node.attrs:
                item.update(layout=node.attrs["data-sf-layout"], offsets=layout_offsets(node))
            if item["kind"] == "text":
                item["text"] = "".join(TextContent(deck.inner(node)).values)
            if item["kind"] == "image":
                item["crop"] = json_value(node.attrs["data-sf-crop"], "crop")
                image = next(child for child in node.children if child.tag == "img")
                item["original"] = image_data(image.attrs["src"])
            objects.append(item)
        result = {"id": identity, "number": list(deck.slides).index(identity) + 1, "notes": deck.meta["notes"].get(identity, ""), "guidance": deck.meta["guidance"].get(identity, {"text": "", "status": "open"}), "objects": objects, "links": deck.links(slide)}
        if "data-sf-duration" in slide.attrs:
            result["duration"] = float(slide.attrs["data-sf-duration"])
        if "data-sf-part" in slide.attrs:
            result["part"] = slide.attrs["data-sf-part"].strip()
        if "data-sf-part-duration" in slide.attrs:
            result["partDuration"] = float(slide.attrs["data-sf-part-duration"])
        if identity in deck.meta.get("notesFormat", {}):
            result["notesFormat"] = deck.meta["notesFormat"][identity]
        if identity in deck.meta.get("notesProvenance", {}):
            result["notesProvenance"] = deck.meta["notesProvenance"][identity]
        return result

    if selector:
        return redacted({"deckId": deck.meta["deckId"], "revision": deck.meta["revision"], "slide": slide_info(deck.select_slide(selector, True))})
    return redacted({"metadata": deck.meta, "slideCount": len(deck.slides), "slides": [slide_info(slide) for slide in deck.slides.values()], "colorSchemes": [{"id": identity, "label": scheme["label"]} for identity, scheme in deck.schemes.items()]})


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("new", help="Create a fresh deck from an explicit compatible template.")
    create.add_argument("--template", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--title", required=True)
    for command in ("inspect", "set-text", "guidance", "scheme", "extract-slide", "replace-slide", "insert-slide", "reorder", "validate", "upgrade-editor"):
        sub = commands.add_parser(command)
        sub.add_argument("file")
        if command not in {"inspect", "validate"}:
            sub.add_argument("--output", required=command in {"extract-slide", "upgrade-editor"})
        if command in {"inspect", "guidance", "extract-slide", "replace-slide"}:
            sub.add_argument("--slide", required=command != "inspect")
        if command == "set-text":
            sub.add_argument("--element", required=True)
            sub.add_argument("--text", required=True)
        if command == "guidance":
            sub.add_argument("--text")
            sub.add_argument("--status", choices=("open", "addressed"))
        if command == "scheme":
            sub.add_argument("--id", required=True, help="Declared color scheme ID; inspect lists the choices.")
        if command in {"replace-slide", "insert-slide"}:
            sub.add_argument("--fragment", required=True)
        if command == "insert-slide":
            sub.add_argument("--after")
        if command == "reorder":
            sub.add_argument("--order", required=True, help="Complete comma-separated permutation of slide IDs.")
    return parser.parse_args()


def resource_fingerprint(value):
    return hashlib.sha256(value.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def editor_identity(deck, registry):
    css = deck.unique("sf-editor-styles", "style")
    runtime = deck.unique("sf-runtime", "script")
    if css.parent is not deck.head or runtime.parent is not deck.body or runtime.attrs.get("type", "text/javascript") not in {"text/javascript", "application/javascript"}:
        raise DeckError("Common editor resources have an unsupported placement or type.")
    fingerprints = {"cssSha256": resource_fingerprint(deck.inner(css)), "runtimeSha256": resource_fingerprint(deck.inner(runtime))}
    manifests = [node for node in deck.nodes if node.attrs.get("id") == "sf-editor-manifest"]
    manifest = deck.unique("sf-editor-manifest", "script") if manifests else None
    if manifest:
        identity = deck.json_node(manifest)
        if set(identity) != {"schemaVersion", "editorVersion", "cssSha256", "runtimeSha256"} or type(identity["schemaVersion"]) is not int or identity["schemaVersion"] != 1 or not isinstance(identity["editorVersion"], str) or any(not isinstance(identity[key], str) for key in fingerprints):
            raise DeckError("Unsupported editor resource manifest.")
        release = registry["releases"].get(identity["editorVersion"])
        if not release or not release["manifest"] or any(identity[key] != fingerprints[key] or release[key] != fingerprints[key] for key in fingerprints):
            raise DeckError("Unknown, newer, mixed or modified common editor resources.")
    else:
        matches = [value for value in registry["releases"].values() if not value["manifest"] and all(value[key] == fingerprints[key] for key in fingerprints)]
        if len(matches) != 1:
            raise DeckError("Unrecognized unmanifested common editor resources; custom changes cannot be replaced safely.")
    return css, runtime, manifest


def revision_span(deck):
    """Locate the root revision value without reserializing any other metadata."""
    raw = deck.inner(deck.document_node)
    decoder = json.JSONDecoder()
    position = raw.index("{") + 1
    while True:
        while position < len(raw) and raw[position].isspace():
            position += 1
        if raw[position] == "}":
            break
        key, end = decoder.raw_decode(raw, position)
        position = end
        while raw[position].isspace():
            position += 1
        if raw[position] != ":":
            raise DeckError("Invalid metadata member.")
        position += 1
        while raw[position].isspace():
            position += 1
        _, end = decoder.raw_decode(raw, position)
        if key == "revision":
            return deck.document_node.open_end + position, deck.document_node.open_end + end
        position = end
        while raw[position].isspace():
            position += 1
        if raw[position] == ",":
            position += 1
    raise DeckError("Saved revision is missing.")


def upgrade_preserved_source(deck):
    css = deck.unique("sf-editor-styles", "style")
    runtime = deck.unique("sf-runtime", "script")
    edits = [(css.open_end, css.close_start, ""), (runtime.open_end, runtime.close_start, ""), (*revision_span(deck), "")]
    for node in deck.nodes:
        if node.attrs.get("id") == "sf-editor-manifest":
            edits.append((node.start, node.end, ""))
    return patched(deck.source, edits)


def upgrade_editor(deck, source_path, destination):
    source_path, destination = Path(source_path), Path(destination)
    if source_path.resolve() == destination.resolve() or os.path.lexists(destination):
        raise DeckError("upgrade-editor requires a distinct, new output file; the original is retained.")
    assets = Path(__file__).resolve().parents[1] / "assets"
    registry = json_value(read_source(assets / "editor-releases.json"), "trusted editor releases")
    css, runtime, manifest = editor_identity(deck, registry)
    current = Deck(read_source(assets / "consulting-blank.html"))
    next_css, next_runtime, next_manifest = editor_identity(current, registry)
    if next_manifest is None or current.json_node(next_manifest)["editorVersion"] != registry["current"]:
        raise DeckError("Packaged current editor release is inconsistent.")
    revision = str(uuid.uuid4())
    edits = [(css.open_end, css.close_start, current.inner(next_css)), (runtime.open_end, runtime.close_start, current.inner(next_runtime)), (*revision_span(deck), json.dumps(revision))]
    edits.append((manifest.start, manifest.end, current.outer(next_manifest)) if manifest else (runtime.start, runtime.start, current.outer(next_manifest)))
    output = patched(deck.source, edits)
    checked = Deck(output)
    editor_identity(checked, registry)
    if upgrade_preserved_source(deck) != upgrade_preserved_source(checked):
        raise DeckError("Editor update would alter authored source outside the allowed spans.")
    atomic_write(destination, output, source_path, exclusive=True)
    return {"output": str(destination.resolve()), "retainedOriginal": str(source_path.resolve()), "editorVersion": registry["current"], "revision": revision}


def run(args):
    source_path = args.template if args.command == "new" else args.file
    deck = Deck(read_source(source_path))
    if args.command == "upgrade-editor":
        return upgrade_editor(deck, source_path, args.output)
    if args.command == "validate":
        broken = deck.broken_links()
        result = {"valid": not broken, "schemaVersion": 1, "deckId": deck.meta["deckId"], "revision": deck.meta["revision"], "slides": len(deck.slides), "objects": len(deck.objects)}
        if broken:
            result["linkErrors"] = broken
        return result
    if args.command == "inspect":
        return inspection(deck, args.slide)
    if args.command == "extract-slide":
        fragment = deck.outer(deck.select_slide(args.slide, True))
        atomic_write(args.output, fragment, source_path)
        return {"output": str(Path(args.output).resolve()), "slideId": deck.select_slide(args.slide, True).attrs["data-sf-slide"]}
    edits = []
    if args.command == "new":
        deck.meta.update(deckId=str(uuid.uuid4()), title=args.title)
        titles = [node for node in deck.head.children if node.tag == "title"]
        if len(titles) != 1:
            raise DeckError("Template needs exactly one document <title>.")
        edits.append((titles[0].open_end, titles[0].close_start, html.escape(args.title, quote=False)))
        # A starter's design overview slides describe the template; the new deck leaves them out.
        overview = [slide for slide in deck.slides.values() if "data-sf-overview" in slide.attrs]
        if len(overview) == len(deck.slides):
            raise DeckError("Template holds only design overview slides; it needs at least one deck slide.")
        for slide in overview:
            end = slide.end
            while end < len(deck.source) and deck.source[end] in " \t\r\n":
                end += 1
            edits.append((slide.start, end, ""))
            identity = slide.attrs["data-sf-slide"]
            deck.meta["notes"].pop(identity, None)
            deck.meta["guidance"].pop(identity, None)
    elif args.command == "set-text":
        node = deck.objects.get(args.element)
        if node is None or node.attrs["data-sf-kind"] != "text":
            raise DeckError(f"Unknown text-kind object {args.element!r}; inspect current IDs first.")
        if any(other is not node and other.inside(node) for other in deck.objects.values()):
            raise DeckError("Text replacement cannot delete nested editable objects; replace the slide explicitly.")
        edits.append((node.open_end, node.close_start, html.escape(args.text, quote=False)))
    elif args.command == "guidance":
        slide = deck.select_slide(args.slide)
        if args.text is None and args.status is None:
            raise DeckError("guidance needs --text and/or --status.")
        identity = slide.attrs["data-sf-slide"]
        entry = deck.meta["guidance"].setdefault(identity, {"text": "", "status": "open"})
        if args.text is not None:
            entry.update(text=args.text, status="open")
        if args.status is not None:
            entry["status"] = args.status
    elif args.command == "scheme":
        if args.id not in deck.schemes:
            raise DeckError(f"Unknown color scheme {args.id!r}; inspect declared schemes first.")
        deck.meta["colorScheme"] = args.id
        deck.meta.pop("backgroundColor", None)
    elif args.command in {"replace-slide", "insert-slide"}:
        fragment, identity = parse_fragment(args.fragment)
        if args.command == "replace-slide":
            slide = deck.select_slide(args.slide)
            if identity != args.slide:
                raise DeckError("Replacement fragment must retain the target data-sf-slide ID.")
            edits.append((slide.start, slide.end, fragment))
        else:
            if identity in deck.slides:
                raise DeckError(f"Inserted slide ID {identity!r} already exists; supply new unique IDs.")
            insertion = deck.select_slide(args.after).end if args.after is not None else deck.main.close_start
            newline = "\r\n" if "\r\n" in deck.source else "\n"
            edits.append((insertion, insertion, newline + fragment + newline))
            deck.meta["notes"][identity] = ""
            deck.meta["guidance"][identity] = {"text": "", "status": "open"}
    elif args.command == "reorder":
        order = [identity.strip() for identity in args.order.split(",")]
        if len(order) != len(deck.slides) or set(order) != set(deck.slides):
            raise DeckError("--order must be a complete permutation of the current slide IDs, with no duplicates.")
        for node, identity in zip(deck.slides.values(), order):
            edits.append((node.start, node.end, deck.outer(deck.slides[identity])))
    deck.meta["revision"] = str(uuid.uuid4())
    edits.append(deck.metadata_patch())
    output = patched(deck.source, edits)
    checked = Deck(output)  # Whole result is checked BEFORE temp file creation.
    destination = args.output or source_path
    atomic_write(destination, output, source_path)
    result = {"output": str(Path(destination).resolve()), "deckId": checked.meta["deckId"], "revision": checked.meta["revision"], "slides": len(checked.slides)}
    broken = checked.broken_links()
    if broken:
        result["linkWarnings"] = broken
    return result


def main():
    try:
        result = run(arguments())
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("valid") is False else 0
    except (DeckError, OSError, UnicodeError) as error:
        print(f"SlideFactory: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
