from importlib.metadata import version

import ask_the_docs


def test_main_prints_version(capsys):
    ask_the_docs.main()

    assert capsys.readouterr().out == f"atd {version('ask-the-docs')}\n"
    assert ask_the_docs.__version__ == version("ask-the-docs")
