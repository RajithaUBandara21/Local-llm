const PAGE_SIZE = 10;
const MAX_PAGE_BUTTONS = 5;

export { PAGE_SIZE };

function pageNumbers(current: number, total: number): number[] {
  if (total <= MAX_PAGE_BUTTONS) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const half = Math.floor(MAX_PAGE_BUTTONS / 2);
  let start = Math.max(1, current - half);
  const end = Math.min(total, start + MAX_PAGE_BUTTONS - 1);
  start = Math.max(1, end - MAX_PAGE_BUTTONS + 1);
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

export function Pagination({
  page,
  totalItems,
  pageSize = PAGE_SIZE,
  onPageChange,
}: Readonly<{
  page: number;
  totalItems: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
}>) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalPages <= 1) return null;

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="btn btn-sm"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Prev
      </button>
      {pageNumbers(page, totalPages)[0] > 1 && (
        <>
          <button type="button" className="btn btn-sm" onClick={() => onPageChange(1)}>
            1
          </button>
          <span className="pagination-ellipsis">…</span>
        </>
      )}
      {pageNumbers(page, totalPages).map((n) => (
        <button
          key={n}
          type="button"
          className={`btn btn-sm${n === page ? " pagination-current" : ""}`}
          aria-current={n === page ? "page" : undefined}
          onClick={() => onPageChange(n)}
        >
          {n}
        </button>
      ))}
      {pageNumbers(page, totalPages).at(-1)! < totalPages && (
        <>
          <span className="pagination-ellipsis">…</span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => onPageChange(totalPages)}
          >
            {totalPages}
          </button>
        </>
      )}
      <button
        type="button"
        className="btn btn-sm"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </nav>
  );
}
