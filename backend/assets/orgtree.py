"""方案三：部门树模型（组织架构化）
新表 DeptNode：自引用树（id/parent/level/name/full_path）。
现有 Department 表保留（旧数据引用），新树表独立维护。
资产继续挂 Department（叶子=与树节点同名映射），筛选时树节点 → 展开成部门名集合过滤。
"""
from django.db import models


class DeptNode(models.Model):
    """部门组织树节点（最多三级，但模型不限层级）"""
    name = models.CharField('部门名称', max_length=60)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.CASCADE,
                               related_name='children', verbose_name='上级')
    level = models.PositiveSmallIntegerField('层级', default=1)  # 1/2/3
    order = models.PositiveSmallIntegerField('排序', default=0)
    src_names = models.JSONField('原始部门全名', default=list, blank=True,
                                 help_text='挂在该节点下的 Department 全名列表')

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('parent', 'name')]

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        parts, node = [], self
        while node:
            parts.append(node.name)
            node = node.parent
        return ' '.join(reversed(parts))

    def descendant_ids(self):
        """自身+全部子孙 id（两次查询内完成，数据量小直接递归）"""
        ids = [self.id]
        frontier = [self.id]
        while frontier:
            children = list(DeptNode.objects.filter(parent_id__in=frontier).values_list('id', flat=True))
            ids.extend(children)
            frontier = children
        return ids

    def descendant_dept_names(self):
        """子树覆盖的全部原始部门全名（含自身与所有子孙节点的 src_names 并集）"""
        names = set()
        stack = [self]
        while stack:
            node = stack.pop()
            names.update(node.src_names or [])
            stack.extend(node.children.all())
        return names
