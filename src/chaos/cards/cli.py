from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from src.chaos.cards.catalog import CardCatalog, CatalogError
from src.chaos.cards.collector import load_sample_manifest
from src.chaos.cards.enums import SampleScene
from src.chaos.cards.epiphany import split_epiphany_overview
from src.chaos.cards.flash_recognizer import FlashKnowledgeBase, FlashRecognizer
from src.chaos.model import ScreenContext, TextBox

DEFAULT_FLASH_REFERENCE = "datasets/cards/reference/haide_mali/flash_layers.pending.json"
DEFAULT_EPIPHANY_REFERENCE = "datasets/cards/review/haide_mali/epiphany.pending.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ok-chaos 角色牌数据工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("validate-catalog", help="校验角色牌数据库")
    catalog.add_argument("path", nargs="?", default="data/cards", help="卡牌数据库根目录")

    samples = subparsers.add_parser("validate-samples", help="校验采集样本及图片哈希")
    samples.add_argument("path", nargs="?", default="datasets/cards/inbox", help="样本根目录")

    split = subparsers.add_parser("split-epiphany", help="把灵光一闪五分支总览切成独立待审核样本")
    split.add_argument("path", nargs="?", default="datasets/cards/inbox", help="总览样本根目录")
    split.add_argument("--output", help="输出样本根目录；默认写回输入 inbox")

    recognize = subparsers.add_parser("recognize-flash", help="离线识别一份详情页样本的闪光组合")
    recognize.add_argument("manifest", help="待识别样本的 manifest.json")
    recognize.add_argument("--reference", default=DEFAULT_FLASH_REFERENCE, help="闪光候选词库 JSON")
    recognize.add_argument("--epiphany", default=DEFAULT_EPIPHANY_REFERENCE, help="专属灵光一闪词库 JSON")
    recognize.add_argument(
        "--ignore-label",
        action="store_true",
        help="忽略样本中已有 card_id，完全通过卡名 OCR 识别",
    )
    return parser


def _validate_catalog(path: str) -> int:
    try:
        catalog = CardCatalog.from_directory(path)
    except CatalogError as exception:
        print(f"卡牌数据库校验失败: {exception}")
        return 1
    summary = catalog.summary
    print(
        "卡牌数据库校验通过: "
        f"{summary.owners} 个角色, {summary.cards} 张基础牌, "
        f"{summary.variants} 个变体, {summary.source_files} 个数据文件"
    )
    return 0


def _validate_samples(path: str) -> int:
    root = Path(path)
    if not root.exists():
        print(f"样本校验通过: 0 份清单（目录尚未创建: {root}）")
        return 0
    manifests = sorted(root.rglob("manifest.json"))
    failures: list[str] = []
    for manifest in manifests:
        try:
            load_sample_manifest(manifest)
        except (OSError, ValueError) as exception:
            failures.append(f"{manifest}: {exception}")
    if failures:
        print("样本校验失败:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"样本校验通过: {len(manifests)} 份清单")
    return 0


def _split_epiphany(path: str, output: str | None) -> int:
    root = Path(path)
    if not root.exists():
        print(f"灵光一闪切分失败: 样本目录不存在: {root}")
        return 1
    output_root = Path(output) if output else root
    source_paths: list[Path] = []
    failures: list[str] = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        try:
            manifest = load_sample_manifest(manifest_path)
        except (OSError, ValueError) as exception:
            failures.append(f"{manifest_path}: {exception}")
            continue
        if manifest.label.scene is SampleScene.EPIPHANY and not manifest.label.variant_ids:
            source_paths.append(manifest_path)

    created = 0
    existing = 0
    for source_path in source_paths:
        try:
            result = split_epiphany_overview(source_path, output_root)
        except (OSError, ValueError) as exception:
            failures.append(f"{source_path}: {exception}")
            continue
        created += result.created
        existing += result.existing

    if failures:
        print("灵光一闪切分失败:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        f"灵光一闪切分完成: {len(source_paths)} 张总览, "
        f"新建 {created} 个分支样本, 已存在 {existing} 个"
    )
    return 0


def _recognize_flash(
    manifest_path: str,
    reference_path: str,
    epiphany_path: str | None,
    *,
    ignore_label: bool,
) -> int:
    import cv2

    path = Path(manifest_path)
    try:
        manifest = load_sample_manifest(path)
        knowledge = FlashKnowledgeBase.from_reference_files(reference_path, epiphany_path)
        frame = cv2.imread(str(path.parent / manifest.image_path), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError(f"无法读取样本图片: {path.parent / manifest.image_path}")
        texts = tuple(
            TextBox(
                text=item.text,
                x=item.x,
                y=item.y,
                width=item.width,
                height=item.height,
                confidence=float(item.confidence),
            )
            for item in manifest.ocr
        )
        context = ScreenContext(
            frame_id=0,
            captured_at=0.0,
            width=manifest.width,
            height=manifest.height,
            texts=texts,
        )
        result = FlashRecognizer(knowledge).recognize(
            context,
            frame,
            card_id_hint=None if ignore_label else manifest.label.card_id,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exception:
        print(f"闪光识别失败: {exception}")
        return 1
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate-catalog":
        return _validate_catalog(args.path)
    if args.command == "validate-samples":
        return _validate_samples(args.path)
    if args.command == "split-epiphany":
        return _split_epiphany(args.path, args.output)
    if args.command == "recognize-flash":
        return _recognize_flash(
            args.manifest,
            args.reference,
            args.epiphany,
            ignore_label=args.ignore_label,
        )
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
