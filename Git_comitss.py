from datetime import datetime
import pytz
if __name__ == '__main__':
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    now = datetime.now(kyiv_tz)

    formatted_time = now.strftime("%d.%m.%Y/%H:%M")

    git_commands = f"""
git add .
git commit -m "{formatted_time}"
git push
    """

    print(git_commands)
