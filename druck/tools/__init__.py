"""분석 툴 모음. 이 폴더에 .py 파일을 추가하면 자동 등록된다 (_로 시작하는 파일은 제외)."""

KB = "https://chian.io/projects/stanley-druckenmiller"


def src(label: str, slug: str) -> tuple[str, str]:
    return (label, f"{KB}/{slug}")
