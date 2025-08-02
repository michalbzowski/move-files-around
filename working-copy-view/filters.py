def format_bytes(value):
    if not isinstance(value, (int, float)):
        return value
    if value < 1024:
        return f"{value} B"
    elif value < 1024 ** 2:
        return f"{value / 1024:.1f} KB"
    else:
        return f"{value / (1024 ** 2):.2f} MB"


app.jinja_env.filters['format_bytes'] = format_bytes