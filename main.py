import sys, os

# Lancer directement bot.py comme script principal
os.chdir(os.path.dirname(os.path.abspath(__file__)))
exec(open("bot.py", encoding="utf-8").read(), {"__name__": "__main__", "__file__": "bot.py"})
