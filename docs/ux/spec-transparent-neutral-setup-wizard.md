# 透明的中性设置向导

## Problem Statement

设置向导第一步目前要求用户选择“学制模板”，但系统只提供“初中（空白模板）”一个选项。这个选项既看不到将生成什么，也不会真正决定学校的学制：创建学期时它会偷偷写入一批初中科目和一张空作息表，而班级的学制实际上可以混合设置。用户因此无法判断选择的用途，也容易把初始化预设误认为学校级学制配置。

向导完成后还存在两个断点：基础数据导入需要用户理解多个文件之间的隐含顺序；完成页只显示数量，不能说明哪些条件还未满足；系统管理中的“重新启动设置向导”会清空向导绑定的学期，和已有数据并存时容易造成重复创建。

## Solution

把向导改为透明的四步初始设置流程：

1. **学校与学期**：显示学校名称，填写学年、学期、学期起止日期；只创建学期外壳。
2. **基础数据**：默认使用包含科目、教师、班级、教室/场地四张工作表的组合 Excel，也可以切换到按依赖顺序的手工录入。
3. **作息安排**：根据已导入班级给出作息分组建议；用户可以合并、拆分并确认分组，再用带周视图预览的作息配置器建立作息时间表。
4. **完成检查**：区分必须完成项和建议提醒，提供返回修改入口；完成只表示基础设置完成，并进入教学任务管理。

“学校模板”从新建学期和新增作息时间表中移除。所有快捷起稿都以可见参数、完整预览和显式确认的方式提供，不按学校学制隐式写入数据。

## User Stories

1. As a first-time scheduling administrator, I want the first step to explain exactly what will be created, so that I do not have to guess what a school template means.
2. As a first-time scheduling administrator, I want to create a semester without receiving hidden subjects or a hidden timetable, so that the initial data reflects my school.
3. As a scheduling administrator, I want to see the current school name while setting up a semester, so that I know which school's data I am editing.
4. As a scheduling administrator, I want invalid or missing semester dates to be reported before continuing, so that later calendar and leave operations have a valid range.
5. As a scheduling administrator, I want one workbook for the initial data, so that I do not have to discover the dependency order between subjects, teachers, and classes.
6. As a scheduling administrator, I want to preview additions, unchanged rows, changed rows, and conflicts before import, so that I can correct the workbook without polluting the semester.
7. As a scheduling administrator, I want the complete workbook import to be transactional, so that a failed reference does not leave half of the school data written.
8. As a small-school administrator, I want a guided manual-entry mode, so that I can enter a few records without preparing a workbook.
9. As a scheduling administrator, I want teacher accounts to be a separate later action, so that initial data setup does not mix account security with school data.
10. As a scheduling administrator, I want the system to suggest timetable groups from imported class information, so that I can configure a mixed school quickly.
11. As a scheduling administrator, I want to merge or split the suggested timetable groups, so that a track label never forces an incorrect timetable.
12. As a scheduling administrator, I want to edit period names, types, and optional bell times while seeing a weekly preview, so that I can verify the timetable before applying it.
13. As a scheduling administrator, I want each class to have an explicit or default timetable assignment, so that no class silently lacks legal scheduling slots.
14. As a scheduling administrator, I want to save and exit at any step, so that an incomplete setup can be resumed from the dashboard.
15. As a scheduling administrator, I want the wizard to distinguish blockers from reminders, so that optional work such as rooms or bell times does not prevent me from creating teaching tasks.
16. As a scheduling administrator, I want the completion page to link directly to each unresolved item, so that I can finish setup without hunting through unrelated pages.
17. As a scheduling administrator, I want completion to take me directly to teaching-task management, so that the next action is obvious.
18. As a system administrator, I want “check and complete the current semester” to reuse the same flow without creating another semester, so that restarting setup is safe.
19. As a director, I want to inspect the setup and its checklist without being able to modify it, so that read-only oversight remains consistent with existing role permissions.
20. As a scheduling administrator, I want progress indicators to reflect actual data, so that a clicked step cannot appear complete when its required data is missing.

## Implementation Decisions

- The setup wizard has four steps: school and semester, base data, timetable arrangement, and completion check. The stored last-visited step is navigation aid only; step completion is derived from the current semester data.
- A new semester created through the setup flow has no template key, no subjects, and no period table. Its lifecycle remains preparing/draft and it becomes the current work context using the existing semester-context rules.
- The school-template concept is removed from user-facing semester and period-table creation. The period-table interface instead accepts explicit weekday, period, type, and optional time values and returns a previewable result before applying it.
- The school name is displayed in the first step. System administrators can edit it there; scheduling administrators see it read-only. A configured name is not a new school-level domain entity.
- The initial workbook contains four logical sheets: subjects, teachers, classes, and rooms. References within the workbook are validated before persistence. Teacher account creation is not part of this import.
- Import preview is a public application seam. It reports new, unchanged, changed, and ambiguous records. A confirmed import applies the whole workbook atomically; ambiguous identities and invalid references block confirmation. No automatic destructive replacement is provided.
- Manual entry uses the existing base-data capabilities behind a guided order: subjects, teachers, classes, then rooms. A transparent, unchecked common-subject list may accelerate entry, but it is never tied to a school-track bundle or written without confirmation.
- Imported class tracks are used only to propose timetable groups. Users can merge and split groups; each class ultimately resolves to a timetable explicitly or through the semester default. A timetable group is not a new school-level academic system.
- The timetable builder supports regular periods plus optional morning, lunch, homeroom, and reserved period types. Period names and types are required; start/end times may be absent with a completion reminder. At least one regular period is required to clear the setup blocker.
- Completion blockers are: valid semester dates, at least one subject, teacher, and class, at least one regular period, and no unresolved timetable or import conflicts. Missing rooms, teacher accounts, special dates, or bell times are reminders and require an explicit acknowledgement if the user finishes with them outstanding.
- Finishing the wizard marks initial setup complete and routes to teaching-task management. It does not mark the semester's later scheduling-readiness confirmation or publish a timetable.
- “Restart wizard” becomes “check and complete the current semester”: it binds to the current writable semester, preserves all data, jumps to the first incomplete step, and never creates a duplicate semester. The existing new-semester copy flow remains separate.
- Save-and-exit preserves progress; the dashboard exposes a resume action while setup is incomplete. A completed initial setup is not revoked merely because later data is edited; later scheduling-readiness checks remain authoritative.
- Existing deployed-data migration is out of scope for this change; the current repository is treated as not yet deployed with the old template behavior.

## Testing Decisions

- Tests observe public behavior at three seams: semester creation and period configuration endpoints, the combined import preview/confirmation interface, and the browser-visible setup wizard flow.
- Backend tests cover neutral semester creation, atomic workbook validation/confirmation, duplicate and ambiguous identity handling, timetable-group assignments, setup blockers/reminders, and safe current-semester re-entry.
- Frontend tests cover the four-step navigation, role read-only behavior, save-and-exit/resume, visible preview states, grouping confirmation, and completion links. Tests assert user-observable labels and actions rather than Vue private state.
- End-to-end tests run a first-use journey through semester creation, workbook/manual data setup, timetable preview, completion, and navigation to teaching-task management. A second journey re-enters an existing semester and verifies no duplicate is created.
- Existing API, component, and Playwright test conventions remain the prior art; each vertical ticket adds a focused red test before implementation.

## Out of Scope

- Creating or managing teacher login accounts during the initial data import.
- Creating teaching tasks, running the solver, publishing a timetable, or changing the scheduling engine.
- Automatically inferring school calendar dates, special dates, or regional academic rules.
- School-type-specific bundles that silently create subjects or timetable rules.
- Migration or cleanup of data created by an older deployed template flow.
- Replacing the existing semester-copy workflow for opening a new academic term.

## Further Notes

- The domain decision is recorded in ADR-0007. The existing five-step ADR remains historical for the prior shipped flow; the new four-step behavior supersedes its step structure and restart semantics.
- User-facing documentation and responsive screenshots must use “学校与学期” and “基础设置完成” language and must not describe a school template as a school-wide academic-system choice.
