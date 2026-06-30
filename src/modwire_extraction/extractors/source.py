from typing import Literal

from pydantic import BaseModel, Field


ImportCrossingType = Literal["module", "symbol"]
SourceVisibility = Literal["public", "protected", "private"]
SourceSignatureKind = Literal["call", "construct", "index"]
SourceValueDeclarationKind = Literal["assignment", "constant", "property", "unknown"]
SourceValueKind = Literal["callable", "class", "literal", "object", "unknown"]
SourceParameterKind = Literal["positional", "vararg", "keyword_only", "kwarg"]
SourceCallableKind = Literal[
    "function",
    "method",
    "classmethod",
    "staticmethod",
    "constructor",
    "callable_value",
    "anonymous",
]
SourceCallResolution = Literal["resolved", "unresolved", "external", "dynamic"]
SourceExportKind = Literal[
    "module",
    "class",
    "interface",
    "type",
    "abstract_class",
    "function",
    "value",
    "unknown",
]


class SourceImportedSymbol(BaseModel):
    name: str
    alias: str
    is_aliased: bool
    is_default: bool
    is_namespace: bool
    is_star: bool


class SourceImport(BaseModel):
    path: str
    is_relative: bool
    normalized_path: str
    imported_name: str
    is_aliased: bool
    crossing_type: ImportCrossingType
    file_barrier_crossed: bool
    statement_id: int
    join_key: str
    uses_joined_import: bool
    imported_symbols: list[SourceImportedSymbol] = Field(default_factory=list)


class SourceExport(BaseModel):
    name: str
    local_name: str
    kind: SourceExportKind
    crossing_type: ImportCrossingType
    path: str
    is_relative: bool
    normalized_path: str
    is_reexport: bool
    is_default: bool
    is_aliased: bool
    statement_id: int


class SourceFunction(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    line_count: int
    declared_args: int
    optional_args: int


class SourceValue(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    line_count: int
    declaration_kind: SourceValueDeclarationKind
    value_kind: SourceValueKind
    declared_args: int = 0
    optional_args: int = 0


class SourceParameter(BaseModel):
    name: str
    annotation: str = ""
    kind: SourceParameterKind
    has_default: bool = False


class SourceCallable(BaseModel):
    id: str
    source_id: str
    name: str
    qualified_name: str
    owner_name: str = ""
    kind: SourceCallableKind
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    line_start: int
    line_end: int
    line_count: int
    parameters: list[SourceParameter] = Field(default_factory=list)
    declared_args: int = 0
    optional_args: int = 0
    return_annotation: str = ""
    decorators: list[str] = Field(default_factory=list)
    docstring: str = ""


class SourceCall(BaseModel):
    source_callable_id: str
    target_callable_id: str = ""
    source_id: str
    line: int
    expression: str
    resolution: SourceCallResolution
    target_name: str


class SourceClassMethod(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    line_count: int
    declared_args: int
    optional_args: int


class SourceClassProperty(BaseModel):
    name: str
    is_optional: bool


class SourceSignature(BaseModel):
    kind: SourceSignatureKind
    line_count: int
    declared_args: int
    optional_args: int


class SourceClass(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    methods: list[SourceClassMethod]
    properties: list[SourceClassProperty]
    line_count: int


class SourceInterface(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    methods: list[SourceClassMethod]
    properties: list[SourceClassProperty]
    signatures: list[SourceSignature]
    line_count: int


class SourceType(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    properties: list[SourceClassProperty]
    signatures: list[SourceSignature]
    line_count: int


class SourceAbstractClass(BaseModel):
    name: str
    visibility: SourceVisibility
    visibility_intent: SourceVisibility
    abstract_methods: list[SourceClassMethod]
    concrete_methods: list[SourceClassMethod]
    properties: list[SourceClassProperty]
    line_count: int


class SourceFile(BaseModel):
    imports: list[SourceImport]
    exports: list[SourceExport] = Field(default_factory=list)
    classes: list[SourceClass]
    interfaces: list[SourceInterface] = Field(default_factory=list)
    types: list[SourceType] = Field(default_factory=list)
    abstract_classes: list[SourceAbstractClass] = Field(default_factory=list)
    functions: list[SourceFunction]
    values: list[SourceValue] = Field(default_factory=list)
    callables: list[SourceCallable] = Field(default_factory=list)
    calls: list[SourceCall] = Field(default_factory=list)
    line_count: int
    code_line_count: int
    public_symbol_count: int
