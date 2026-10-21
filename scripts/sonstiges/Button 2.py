# --- Plugin-Parameter (neues System) ---
NAME = "Button 2"
DESCRIPTION = "Demo: startet als eigenes Programm in einem separaten Prozess."
ICON = "🔘"
RUN_AS = "process"  # kein PluginWidget – läuft als eigener Prozess
# ----------------------------------------

def test():
    print("Test 2")

test()