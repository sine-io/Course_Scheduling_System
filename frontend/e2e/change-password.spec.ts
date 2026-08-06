import { expect, test } from '@playwright/test'

/**
 * 首次登录强制改密——**每一位新用户进入系统的第一个画面**。
 *
 * 为什么值得一支专属测试:这一页只有在「被强制改密」的状态下进得去(路由守卫会把
 * 非强制状态的人导回仪表板),先前所有测试都是走 API 改密码,从没有人点过这个画面。
 * 而 v1.1.1 修掉的那只虫(系统管理页整页渲染失败)正是这样溜过两个版本的——
 * 没有 e2e 覆盖的页面,坏掉时没有任何人会知道。这一页若坏了,新用户连门都进不来。
 *
 * 账号 e2e_newuser 由 seed_e2e 每次重设回「首次登录」状态(本测试会把它用掉)。
 */

const USER = 'e2e_newuser'
const OLD_PW = 'e2enewuser1234'
const NEW_PW = 'e2echanged5678'

const SHOTS = 'e2e/screenshots'

test('首次登录:强制改密页阻止去路、验证输入,改完才能进入系统', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('请输入账号').fill(USER)
  await page.getByPlaceholder('请输入密码').fill(OLD_PW)
  await page.getByRole('button', { name: '登录' }).click()

  // ① 登录后被导到改密页,而且**页面真的渲染出来**(这是本测试的核心:整页空白就必红)
  await page.waitForURL(/change-password/, { timeout: 15_000 })
  await expect(page.getByText('修改密码')).toBeVisible()
  await expect(page.getByTestId('cp-forced')).toContainText('首次登录')
  await expect(page.getByTestId('cp-submit')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/cp-1-forced.png` })

  // ② 后端也挡(不是只有前端导向):未改密前功能性 API 一律 403
  const blocked = await page.request.get('/api/semesters')
  expect(blocked.status(), '强制改密期间后端就该阻止,不能只靠前端守卫').toBe(403)

  // ③ 想绕过去看别页?守卫会把人送回来
  await page.goto('/')
  await page.waitForURL(/change-password/, { timeout: 15_000 })

  const oldInput = page.getByTestId('cp-old').locator('input')
  const newInput = page.getByTestId('cp-new').locator('input')
  const confirmInput = page.getByTestId('cp-confirm').locator('input')

  // ④ 新密码太短 → 前端就阻止,不必等后端。
  //    顺带守住「一次提交只跑一次」:按钮先前同时挂了 submit 与 @click,每次提交跑两遍,
  //    在成功路径上等于提交两次改密请求,第二次必然回「原密码错误」。
  await oldInput.fill(OLD_PW)
  await newInput.fill('short')
  await confirmInput.fill('short')
  await page.getByTestId('cp-submit').click()
  const tooShort = page.getByText('新密码至少需要 8 个字符')
  await expect(tooShort.first()).toBeVisible()
  expect(await tooShort.count(), '同一次提交不该出现两则消息(重复触发)').toBe(1)

  // ⑤ 两次输入不一致(最常见的手误)。这里用 Enter 提交,顺便确认键盘操作也走得通
  await newInput.fill(NEW_PW)
  await confirmInput.fill(`${NEW_PW}x`)
  await confirmInput.press('Enter')
  const mismatch = page.getByText('两次输入的新密码不一致')
  await expect(mismatch.first()).toBeVisible()
  expect(await mismatch.count(), '同一次提交不该出现两则消息(重复触发)').toBe(1)

  // ⑥ 原密码打错 → 后端的消息要真的传到画面上(不是笼统的「变更密码失败」)
  await oldInput.fill('wrongpassword')
  await confirmInput.fill(NEW_PW)
  await page.getByTestId('cp-submit').click()
  await expect(page.getByText('原密码错误')).toBeVisible()

  // ⑦ 正确填写 → 改密成功并离开这一页
  await oldInput.fill(OLD_PW)
  await newInput.fill(NEW_PW)
  await confirmInput.fill(NEW_PW)
  await page.getByTestId('cp-submit').click()
  await expect(page.getByText('密码已更新')).toBeVisible()
  await expect(page).not.toHaveURL(/change-password/)

  // ⑧ 改完之后 API 就通了(强制状态确实解除,不是只有画面跳走)
  await expect.poll(async () => (await page.request.get('/api/semesters')).status())
    .toBe(200)

  // ⑨ 新密码真的能用,而且不会再被要求改密
  await page.request.post('/api/auth/logout')
  await page.goto('/login')
  await page.getByPlaceholder('请输入账号').fill(USER)
  await page.getByPlaceholder('请输入密码').fill(NEW_PW)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15_000 })
  await expect(page).not.toHaveURL(/change-password/)
})
