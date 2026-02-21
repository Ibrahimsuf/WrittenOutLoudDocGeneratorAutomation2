from memory_profiler import memory_usage
from app import generate_pdf
from utils import add_page_numbers_to_pdf

if __name__ == "__main__":
    before = memory_usage(-1, interval=0.1, timeout=1)[0]

    mem_usage = memory_usage(
        (generate_pdf,
         ("https://docs.google.com/document/d/14yRJbtXc-93kOqI77E9A98nz-o1D6gamvLpXK8G82tk/edit?tab=t.0", "Sample Title", "Alice, Bob", "Charlie", "crew123", "In memory of..."),),
        interval=0.1
    )
    # mem_usage = memory_usage(
    # (add_page_numbers_to_pdf, ("downloads/THE ANIMAL CHRONICLES: Three Worlds.pdf", "downloads/THE ANIMAL CHRONICLES: Three Worlds_with_pages.pdf")),
    # interval=0.1)

    after = max(mem_usage)

    print("Baseline:", before)
    print("Peak:", after)
    print("Actual Increase:", after - before, "MB")