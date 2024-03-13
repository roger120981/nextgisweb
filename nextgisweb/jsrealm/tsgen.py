from __future__ import annotations

import re
from datetime import datetime, time
from functools import partial
from itertools import count
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from importlib_metadata._itertools import unique_everseen
from msgspec import UNSET, Struct, UnsetType, field
from typing_extensions import Protocol

from nextgisweb.env.package import pkginfo
from nextgisweb.lib.apitype import disannotate
from nextgisweb.lib.apitype.util import NoneType, get_class_annotations, is_enum, is_struct
from nextgisweb.lib.imptool import module_from_stack
from nextgisweb.lib.json import dumps

from .util import indented

ModuleName = str
TypeName = str
Export = Tuple[ModuleName, TypeName]
POST_INIT = cast(Any, UNSET)


class TSGenerator:
    modules: Dict[str, TSModule]
    types: Dict[Any, TSType]

    def __init__(self):
        self.counter = count(0)
        self.types = dict()
        self.modules = dict()

    def module(self, name: ModuleName) -> TSModule:
        if (module := self.modules.get(name)) is None:
            module = TSModule(generator=self, name=name)
            self.modules[name] = module
        return module

    def add(self, tdef: Any, *, export: Union[Export, None] = None) -> TSType:
        otype, annotations = disannotate(tdef)

        if (result := self.types.get(otype)) is None:
            result = self.translate(otype)
            if (
                export is None
                and result.auto_export
                and (name := getattr(otype, "__name__", None))
                and (module := getattr(otype, "__module__", None))
            ):
                cid = pkginfo.component_by_module(module)
                if not name.startswith("_") and cid:
                    result.add_export((component_tsmodule(cid), name))

        for ann in annotations:
            if isinstance(ann, TSExport):
                result.add_export((ann.module, ann.name_for(otype)))

        if export is not None:
            result.add_export(export)

        return result

    def translate(self, otype: Any) -> TSType:
        defaults: Any = dict(generator=self, type=otype)

        if otype is UnsetType:
            result = TSPrimitive(keyword="never", **defaults)
        elif otype is NoneType:
            result = TSPrimitive(keyword="null", **defaults)
        elif otype is Any:
            result = TSPrimitive(keyword="unknown", **defaults)
        elif otype in (int, float):
            result = TSPrimitive(keyword="number", comment=otype.__name__, **defaults)
        elif otype is bool:
            result = TSPrimitive(keyword="boolean", **defaults)
        elif otype is str:
            result = TSPrimitive(keyword="string", **defaults)
        elif otype in (bytes, datetime, time):
            result = TSPrimitive(keyword="string", comment=otype.__name__, **defaults)
        elif is_enum(otype):
            result = TSEnum(args=[m.value for m in otype], **defaults)
        elif is_struct(otype):
            args = struct_fields_encoded(otype)
            if otype.__struct_config__.array_like:
                result = TSStructArray(args=args, **defaults)
            elif len(args) == 0:
                result = TSPrimitive(keyword="Record<string, never>", **defaults)
            else:
                result = TSStructObject(args=args, **defaults)
        elif (origin := get_origin(otype)) is Union:
            result = TSUnion(args=get_args(otype), **defaults)
        elif origin is list:
            result = TSList(arg=get_args(otype)[0], **defaults)
        elif origin is tuple:
            result = TSTuple(args=get_args(otype), **defaults)
        elif origin is dict:
            result = TSMapping(args=get_args(otype), **defaults)
        elif otype is dict:
            result = TSMapping(args=(str, Any), **defaults)
        elif origin is Literal:
            result = TSEnum(args=get_args(otype), **defaults)
        else:
            result = TSPrimitive(keyword="unknown", comment=str(otype), **defaults)
        return result

    def register(self, ts: TSType):
        self.types[ts.type] = ts

    def compile(self) -> Sequence[TSModuleCompiled]:
        return tuple(m.compile() for m in self.modules.values())


class TSModule(Struct, kw_only=True, dict=True):
    generator: TSGenerator
    name: ModuleName
    unique: int = POST_INIT

    imports: Set[TSModule] = field(default_factory=set)
    declared: List[TSType] = field(default_factory=list)
    exported: List[Tuple[TSType, TypeName]] = field(default_factory=list)
    code: Union[str, None] = None

    def __post_init__(self):
        self.unique = next(self.generator.counter)

    def __hash__(self) -> int:
        return hash((id(self.generator), self.unique))

    @property
    def ns(self) -> str:
        return f"ns{self.unique}"

    def compile(self) -> TSModuleCompiled:
        declarations = ["export {};"]
        declarations.extend(f"export type {t.name} = {t.inline(self)};" for t in self.declared)

        exports = list()
        for t, name in self.exported:
            if name == "default":
                exports.append(f"export default {t.reference(self)};")
            else:
                exports.append(f"export type {name} = {t.reference(self)};")

        imports = [f'import type * as {m.ns} from "{m.name}";' for m in self.imports]

        lines = list()
        for a in (imports, declarations, exports):
            if len(a) > 0:
                lines.extend(([""] if (lines and lines[-1] != "") else []) + a)

        self.code = f'declare module "{self.name}" {{\n{indented(lines)}\n}}\n'
        return cast(TSModuleCompiled, self)


class TSModuleCompiled(Protocol):
    name: ModuleName
    code: str


class TSType(Struct, kw_only=True, dict=True):
    generator: TSGenerator
    unique: int = POST_INIT
    type: Any

    module: Union[TSModule, None] = None
    name: Union[TypeName, None] = None
    comment: Union[str, None] = None

    auto_export: bool = False

    def __post_init__(self):
        self.unique = next(self.generator.counter)
        self.generator.register(self)
        self.__tstype_init__()

    def __tstype_init__(self):
        pass

    def __hash__(self) -> int:
        return hash((id(self.generator), self.unique))

    def add_export(self, value: Tuple[ModuleName, TypeName]):
        module = self.generator.module(value[0])
        if self.module is None:
            self.module, self.name = module, value[1]
            module.declared.append(self)
        elif value != (self.module.name, self.name):
            module.exported.append((self, value[1]))

    def render(self, module: TSModule) -> str:
        if self.module is None or isinstance(self, TSPrimitive):
            result = self.inline(module) + (f" /* {rem} */" if (rem := self.comment) else "")
        else:
            result = self.reference(module)
        return result

    def inline(self, module: TSModule) -> str:
        raise NotImplementedError

    def reference(self, module: TSModule) -> str:
        assert self.module is not None and self.name is not None
        if module == self.module:
            return self.name
        else:
            module.imports.add(self.module)
            return f"{self.module.ns}.{self.name}"


class TSPrimitive(TSType, kw_only=True):
    keyword: str = "unknown"

    def inline(self, module: TSModule) -> str:
        return self.keyword


class TSUnion(TSType, kw_only=True):
    args: Sequence[Any]
    items: Tuple[TSType, ...] = POST_INIT
    undefided_excluded: Union[TSType, None] = POST_INIT

    def __tstype_init__(self):
        super().__tstype_init__()
        self.items = tuple(self.generator.add(i) for i in unique_everseen(self.args))
        args_defined = tuple(a for a in self.args if a is not UnsetType)
        if len(self.args) != len(args_defined):
            if len(args_defined) > 1:
                dtype = Union[args_defined]  # type: ignore
                self.undefided_excluded = TSUnion(
                    args=args_defined,
                    type=dtype,
                    generator=self.generator,
                )
            else:
                for itm in self.items:
                    if itm.type is not UnsetType:
                        self.undefided_excluded = itm
                        break
                assert self.undefided_excluded is not UNSET
        else:
            self.undefided_excluded = None

    def inline(self, module: TSModule) -> str:
        return " | ".join(ts.render(module) for ts in self.items)


class TSEnum(TSType, kw_only=True):
    args: Sequence[Union[str, int, bool]]
    auto_export = True

    def inline(self, module) -> str:
        return "({})".format(" | ".join(dumps(a) for a in self.args))


class TSList(TSType, kw_only=True):
    arg: Any
    item: TSType = POST_INIT

    def __tstype_init__(self):
        super().__tstype_init__()
        self.item = self.generator.add(self.arg)

    def inline(self, module: TSModule) -> str:
        return "({})[]".format(self.item.render(module))


class TSTuple(TSType, kw_only=True):
    args: Tuple[Any, ...]
    items: Tuple[TSType, ...] = POST_INIT

    def __tstype_init__(self):
        super().__tstype_init__()
        self.items = tuple(self.generator.add(a) for a in self.args)

    def inline(self, module: TSModule) -> str:
        parts = [i.render(module) for i in self.items]
        return f"[{', '.join(parts)}]"


class TSStructObject(TSType, kw_only=True):
    args: Mapping[str, Any]
    fields: Tuple[Tuple[str, bool, TSType], ...] = POST_INIT
    auto_export = True

    def __tstype_init__(self):
        super().__tstype_init__()
        fields = list()
        for k, v in self.args.items():
            ts, cu = self.generator.add(v), False
            if isinstance(ts, TSUnion) and (ts_ue := ts.undefided_excluded) is not None:
                ts, cu = ts_ue, True
            fields.append((k, cu, ts))
        self.fields = tuple(fields)

    def inline(self, module: TSModule) -> str:
        q = lambda v: v if re.match(r"\w+$", v) else f"[{dumps(v)}]"
        parts = [f"{q(k)}{'?' if ue else ''}: {ts.render(module)}" for k, ue, ts in self.fields]
        indented_sc = partial(indented, sep=";\n")
        return f"{{\n{indented_sc(parts)};\n}}" if len(self.fields) > 1 else f"{{ {parts[0]} }}"


class TSStructArray(TSType, kw_only=True):
    args: Mapping[str, Any]
    fields: Tuple[Tuple[str, TSType], ...] = POST_INIT
    auto_export = True

    def __tstype_init__(self):
        super().__tstype_init__()
        self.fields = tuple((k, self.generator.add(v)) for k, v in self.args.items())

    def inline(self, module: TSModule) -> str:
        parts = [f"{k}: {v.render(module)}" for k, v in self.fields]
        return f"[{', '.join(parts)}]"


class TSMapping(TSType, kw_only=True):
    args: Tuple[Any, Any]
    ktype: TSType = POST_INIT
    vtype: TSType = POST_INIT

    def __tstype_init__(self):
        super().__tstype_init__()
        self.ktype, self.vtype = [self.generator.add(a) for a in self.args]

    def inline(self, module: TSModule) -> str:
        return f"Record<{self.ktype.render(module)}, {self.vtype.render(module)}>"


T = TypeVar("T")


class TSExport:
    name: Union[str, None]
    module: str

    def __init__(
        self,
        name: Union[str, None] = None,
        *,
        component: Union[str, None] = None,
        module: str = "type/api",
        depth: int = 0,
    ):
        self.name = name
        if not module.startswith("@"):
            if component is None:
                mod = module_from_stack(depth + 1, (__name__,))
                component = pkginfo.component_by_module(mod)
                if component is None:
                    raise TypeError(f"no component found for module: {mod}")
            module = component_tsmodule(component, module)
        self.module = module

    def __hash__(self):
        return hash((self.module, self.name))

    def name_for(self, type: Any) -> str:
        if (name := self.name) is not None:
            return name
        if (name := getattr(type, "__name__", None)) is not None:
            return name
        raise TypeError(f"Unable to determine name for {type}")


def component_tsmodule(component: str, module: str = "type/api") -> str:
    parts = ("@nextgisweb", component.replace("_", "-"), module)
    return "/".join(parts)


def struct_fields_encoded(otype) -> Dict[str, Any]:
    hints = get_class_annotations(otype)
    return {
        en: hints[fn]
        for fn, en in zip(
            otype.__struct_fields__,
            otype.__struct_encode_fields__,
        )
    }
