from application import run_app


if __name__ == "__main__":
    import faulthandler

    faulthandler.enable()  # 会打印崩溃时的 C 堆栈
    run_app()