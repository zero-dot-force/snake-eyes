"""ContainerMutation fixture: xs is bound locally — not self.* and not a parameter."""


def local_container() -> None:
    xs: list[int] = []
    xs.append(1)  # ContainerMutation (local variable)
    xs.extend([2, 3])  # ContainerMutation (local variable)
