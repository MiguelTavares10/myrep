# -*- coding: utf-8 -*-
__all__ = ("ROSField", "ROSMsgFormat")

import re
from typing import Any, Dict, List, Optional

import attr
import hashlib
import os
import re
import typing as t  # noqa  # This is a mypy workaround
from abc import ABC, abstractmethod
from io import BytesIO
import toposort
from typing import (
    Any,
    BinaryIO,
    Collection,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)
#from .base import Duration, is_builtin, Time
import msg
import base

R_COMMENT = r"(#.*)?"
R_BLANK = re.compile(f"^\s*{R_COMMENT}$")

@attr.s(frozen=True, str=False, slots=True, auto_attribs=True)
class Field:
    """Provides an immutable description of a message field.

    Attributes
    ----------
    typ: str
        The name of the type used this field.
    name: str
        The name of this field.
    """

    R_TYPE = r"[a-zA-Z0-9_/]+(?:\[(?:<=)?\d*\])?"
    R_NAME = r"[a-zA-Z0-9_/]+"
    R_FIELD = re.compile(f"^\s*({R_TYPE})\s+({R_NAME})\s*{R_COMMENT}$")

    typ: str
    name: str

    @classmethod
    def from_string(cls, package: str, line: str) -> "Optional[Field]":
        """
        Produce a field from a string, checking first if it is a
        valid field, otherwise None.

        Parameters
        ----------
        package: str
            The name of the package that provides the field.
        line: str
            The line of text containing the field.

        Returns
        -------
        Optional[Field]
            A Field object if the line is a constant, None otherwise.
        """
        m_field = cls.R_FIELD.match(line)

        if m_field:
            typ, name_field = m_field.group(1, 2)

            typ = cls._resolve_type(package, typ)

            field: Field = Field(typ, name_field)
            return field
        return None

    @classmethod
    def _resolve_type(cls, package: str, typ: str) -> str:
        # resolve the type of the field
        typ_resolved = typ
        base_typ = typ.partition("[")[0]
        if typ == "Header":
            typ_resolved = "std_msgs/Header"
        elif "/" not in typ and not base.is_builtin(base_typ):
            typ_resolved = f"{package}/{typ}"

        if typ != typ_resolved:
            typ = typ_resolved
        return typ

    @property
    def length(self) -> Optional[int]:
        if not self.is_array:
            return None
        sz = self.typ.partition("[")[2].partition("]")[0]
        if sz == "":
            return None
        elif sz.startswith("<="):
            sz = sz[2:]
        return int(sz)

    @property
    def base_type(self) -> str:
        return self.typ.partition("[")[0] if self.is_array else self.typ

    @property
    def base_typ(self) -> str:
        return self.base_type

    def __str__(self) -> str:
        return f"{self.typ} {self.name}"


@attr.s(frozen=True, str=False, slots=True, auto_attribs=True)
class ROSField(Field):
    R_TYPE = (r"[a-zA-Z_/][a-zA-Z0-9_/]*"
              r"(?P<strbounds><=\d+)?(?:\[(?:<=)?\d*\])?")
    R_DEFAULT_VALUE = r"[^#]*"
    R_FIELD = re.compile(f"^\s*(?P<type>{R_TYPE})"
                         f"\s+(?P<name>{Field.R_NAME})(?:\s+)?"
                         f"(?P<val>{R_DEFAULT_VALUE}){R_COMMENT}")
    REXP_TYPE = re.compile(R_TYPE)

    default_value: Optional[str]

    @classmethod
    def from_string(cls, package: str, line: str) -> Optional["ROSField"]:
        m_field = cls.R_FIELD.match(line)
        if m_field:
            typ = m_field.group('type')
            name = m_field.group('name')
            typ = cls._resolve_type(package, typ)
            default_value = m_field.group('val')
            field = ROSField(typ,
                              name,
                              default_value if default_value else None)
            return field
        return None

    @classmethod
    def _resolve_type(cls, package: str, typ: str) -> str:

        # The string bounds (string<=123) will be removed to
        # help resolution of the type
        r_type_match = cls.REXP_TYPE.match(typ)
        if r_type_match and r_type_match.group('strbounds'):
            typ = typ.replace(r_type_match.group('strbounds'), '')
        return super()._resolve_type(package, typ)


class ROSMsgFormat(msg.MsgFormat[ROSField, msg.Constant]):

    @classmethod
    def from_string(
        cls, package: str, name: str, text: str
    ) -> "ROSMsgFormat":
        fields: List[ROSField] = []
        constants: List[Constant] = []

        for line in text.split("\n"):
            m_blank = R_BLANK.match(line)
            if m_blank:
                continue

            constant = Constant.from_string(line)
            field = ROSField.from_string(package, line)
            if constant:
                constants.append(constant)
            elif field:
                fields.append(field)

        return ROSMsgFormat(package=package,
                             name=name,
                             definition=text,
                             fields=fields,
                             constants=constants)




@attr.s(frozen=True, slots=True, str=False, auto_attribs=True)
class Constant:
    """Provides an immutable definition of a constant for a message format.

    Attributes
    ----------
    typ: str
        The name of the type used by this constant.
    name: str
        The name of this constant.
    value: Union[str, int, float]
        The value of this constant.
    """

    R_STRING_CONSTANT = re.compile("^\s*string\s+(\w+)\s*=\s*(.+)\s*$")
    R_OTHER_CONSTANT = re.compile("^\s*(\w+)\s+(\w+)\s*=\s*([^\s]+).*$")

    typ: str
    name: str
    value: Union[str, int, float]

    @classmethod
    def from_string(cls, line: str) -> "Optional[Constant]":
        """
        Produce a constant from a string, checking first if it is a valid
        constant, otherwise None.

        Parameters
        ----------
        line: str
            The line of text containing the constant.

        Returns
        -------
        Optional[Constant]
            A Constant object if the line is a constant, None otherwise.
        """
        m_string_constant = cls.R_STRING_CONSTANT.match(line)
        m_other_constant = cls.R_OTHER_CONSTANT.match(line)
        if m_string_constant:
            name_const, val = m_string_constant.group(1, 2)
            constant = Constant("string", name_const, val)
            return constant
        elif m_other_constant:
            typ, name_const, val_str = m_other_constant.group(1, 2, 3)
            val = val_str  # FIXME convert value
            constant = Constant(typ, name_const, val)
            return constant
        return None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Constant":
        return Constant(d["type"], d["name"], d["value"])

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.typ, "name": self.name, "value": self.value}

    def __str__(self) -> str:
        return f"{self.typ} {self.name}={str(self.value)}"

FIELD = TypeVar("FIELD", bound=Field)
CONSTANT = TypeVar("CONSTANT", bound=Constant)

@attr.s(frozen=True)
class MsgFormat(ABC, Generic[FIELD, CONSTANT]):
    """Provides an immutable definition of a given ROS message format.

    Attributes
    ----------
    package: str
        The name of the package that defines this message format.
    name: str
        The unqualified name of the message format.
    definition: str
        The plaintext contents of the associated .msg file.
    fields: Sequence[FIELD]
        The fields that belong to this message format.
    constants: Sequence[CONSTANT]
        The named constants that belong to this message format.

    References
    ----------
    * http://wiki.ros.org/msg
    """

    package: str = attr.ib()
    name: str = attr.ib()
    definition: str = attr.ib()
    fields: Tuple[FIELD, ...] = attr.ib(converter=msg.tuple_from_iterable)
    constants: Tuple[CONSTANT, ...] = attr.ib(converter=msg.tuple_from_iterable)

    @classmethod
    def toposort(cls, fmts: Collection["MsgFormat"]) -> List["MsgFormat"]:
        fn_to_fmt: Dict[str, MsgFormat] = {fmt.fullname: fmt for fmt in fmts}
        fn_to_deps: Dict[str, Set[str]] = {
            filename: {
                f.base_typ for f in fmt.fields if not base.is_builtin(f.base_typ)
            }
            for filename, fmt in fn_to_fmt.items()
        }
        toposorted = list(toposort(fn_to_deps))
        missing_packages: Set[str] = set(toposorted) - set(fn_to_fmt)
        if missing_packages:
            missing_package_name = next(iter(missing_packages))
            raise exc.PackageNotFound(missing_package_name)
        return [fn_to_fmt[filename] for filename in toposorted]


    @classmethod
    @abstractmethod
    def from_string(cls, package: str, name: str, text: str) -> "MsgFormat":
        """Constructs a message format from its description.

        Parameters
        ----------
        package: str
            The name of the package that provides the file.
        filename: str
            The absolute path to the .msg file inside the given filesystem.
        text: str
            The message definition itself (e.g., the contents of a .msg file).

        Raises
        ------
        ParsingError
            If the description cannot be parsed.
        """
        ...

    @staticmethod
    def sections_from_string(text: str) -> t.List[str]:
        sections: t.List[str] = [""]
        section_index = 0
        for line in (ss.strip() for ss in text.split("\n")):
            if line.startswith("---"):
                section_index += 1
                sections.append("")
            else:
                sections[section_index] += f"{line}\n"
        return sections

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "package": self.package,
            "name": self.name,
            "definition": self.definition,
        }
        if self.fields:
            d["fields"] = [f.to_dict() for f in self.fields]
        if self.constants:
            d["constants"] = [c.to_dict() for c in self.constants]
        return d

    @property
    def fullname(self) -> str:
        """The fully qualified name of this message format."""
        return f"{self.package}/{self.name}"

    def flatten(
        self,
        name_to_format: Mapping[str, "MsgFormat"],
        ctx: Tuple[str, ...] = (),
    ) -> Iterator[Tuple[Tuple[str, ...], FIELD]]:
        for field in self.fields:
            if field.is_array or is_builtin(field.typ):
                yield (ctx, field)
            else:
                fmt = name_to_format[field.typ]
                yield from fmt.flatten(name_to_format, ctx + (field.name,))




