"""分页辅助。

列表接口统一从这里取分页上限、用同一个函数判断「是否还有下一页」。
之前项目里并存过两种算法（`total > skip + count` 与 `total > page * page_size`），
以及 50 / 100 两种 pageSize 上限 —— 口径不一，调用方不知道该照哪个抄。
"""

MAX_PAGE_SIZE = 100


def calc_has_more(total: int, skip: int, count: int) -> bool:
    """本页之后是否还有下一页。

    用「本页起始偏移 + 本页实际条数」与总数对账，而不是 `page * page_size`：
    直接基于真实返回条数，最后一页不满时不需要额外假设。
    """
    return total > skip + count
