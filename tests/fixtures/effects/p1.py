"""P1 effects fixture: GeneratorYield, AsyncGeneratorYield, ContainerMutation (param), StreamOutput, GlobalMutation."""

_counter = 0


def gen_values():  # type: ignore[return]
    yield 1  # GeneratorYield
    yield 2


async def async_gen():  # type: ignore[return]
    yield "x"  # AsyncGeneratorYield


def param_append(xs: list[int]) -> None:
    xs.append(0)  # PointerArgMutation (param)


def write_file(path: str) -> None:
    f = open(path, "w")  # noqa: WPS515
    f.write("hello")  # StreamOutput + FileSystemWrite


def bump_counter() -> None:
    global _counter
    _counter += 1  # GlobalMutation
