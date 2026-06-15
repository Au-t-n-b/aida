"""Excel importer for schedule input bundles."""

__all__ = ["DataImportError", "load_input_bundle", "write_input_bundle_json"]


def __getattr__(name: str):
    if name in __all__:
        from agent.schedule.importer import excel

        return getattr(excel, name)
    raise AttributeError(name)
