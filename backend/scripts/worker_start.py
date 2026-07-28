"""Worker start placeholder."""


def main() -> None:
    print("Use celery worker -A app.core.celery_app.celery_app -Q normal,high,low,critical")


if __name__ == "__main__":
    main()
