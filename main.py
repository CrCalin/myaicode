import sys

def main():
    args = sys.argv[1:]
    
    if not args or args[0] != "web":
        # If explicitly "tui" is passed, remove it from args
        if args and args[0] == "tui":
            tui_args = args[1:]
        else:
            tui_args = args
            
        from tui import run_tui
        run_tui(tui_args)
    else:
        # Web mode
        web_args = args[1:]
        from web import run_web
        run_web(web_args)

if __name__ == "__main__":
    main()
