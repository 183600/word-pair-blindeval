# 任务1 函数式编程语言 | 条件: baseline | 第 10 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 156.9s | **tokens:** 92/1499

---

# Lumen —— 一门全新的函数式编程语言设计

## 1. 设计哲学

Lumen 的核心理念是:**"显式的纯粹,隐式的优雅"**。

- 一切副作用通过**代数效应(Algebraic Effects)**显式声明
- 类型系统足够强大,但**永远不需要类型标注**(全局类型推断)
- 缩进敏感语法,减少符号噪音
- 编译期保证:**无空指针、无未处理异常、无数据竞争**

---

## 2. 基础语法

```lumen
-- 注释用双横线

-- 函数定义(自动柯里化)
add x y = x + y

-- 管道操作符 |>
result = [1, 2, 3, 4, 5]
  |> map (\x -> x * 2)
  |> filter (\x -> x > 4)
  |> sum        -- 18

-- 模式匹配
describe n = match n
  | 0         -> "zero"
  | x if x < 0 -> "negative"
  | _         -> "positive"

-- 不可变记录,更新用 with
type Person = { name: String, age: Int }

birthday p = p with age = p.age + 1
```

---

## 3. 类型系统

### 3.1 代数数据类型 + 广义代数数据类型(GADT)

```lumen
type Option a
  = Some a
  | None

type Expr a
  = Lit : Int -> Expr Int
  | Add : Expr Int -> Expr Int -> Expr Int
  | Eq  : Expr Int -> Expr Int -> Expr Bool

-- 类型安全的求值器,返回类型由构造器决定
eval : Expr a -> a
eval e = match e
  | Lit n     -> n
  | Add x y   -> eval x + eval y
  | Eq x y    -> eval x == eval y
```

### 3.2 行多态(Row Polymorphism)记录

```lumen
-- 接受任何包含 name 字段的记录
greet : { name: String | r } -> String
greet x = "Hello, " ++ x.name
```

### 3.3 线性类型(可选标注)

```lumen
-- !File 表示线性资源,必须恰好使用一次,编译器保证不泄漏
readFile : !File -> String
```

---

## 4. 代数效应系统(核心特色)

副作用不是 Monad,而是**可声明、可处理、可组合**的效应:

```lumen
-- 声明效应
effect State s
  get : () -> s
  put : s -> ()

effect Console
  print : String -> ()

-- 函数的效应写在类型里,一目了然
increment : () -> Int ! {State Int, Console}
increment () =
  n <- get ()
  put (n + 1)
  print "incremented"
  n

-- 用 handler 处理效应 —— 测试时可以替换实现!
runState : s -> (() -> a ! {State s | e}) -> (a, s) ! e
runState init action = handle action ()
  | return x  -> (x, init)
  | get () k  -> ... -- 续体 k 捕获"程序的剩余部分"
  | put s' k  -> ...

-- 纯函数没有效应标注,编译器强制保证
pureAdd : Int -> Int -> Int   -- 绝不可能有副作用
```

**优势**:测试时注入 mock handler,无需依赖注入框架;并发、异步、异常、日志全部统一为一种机制。

---

## 5. 并发模型

```lumen
-- 结构化并发 + 效应
effect Async
  await : Task a -> a

main = 
  with parallel scope
    t1 = scope.spawn (fetchUser 1)
    t2 = scope.spawn (fetchUser 2)
    -- scope 退出前必须所有任务完成,杜绝孤儿任务
    (await t1, await t2)
```

---

## 6. 编译期元编程

```lumen
-- 编译期求值,零运行时开销
comptime fib 30            -- 编译期算好,直接内联常量

-- 类型级编程
type Vec (n: Nat) a = ...   -- 长度编码在类型里
append : Vec n a -> Vec m a -> Vec (n + m) a
```

---

## 7. 一个完整示例:HTTP 服务

```lumen
effect Http
  route : Method -> Path -> (Request -> Response ! e) -> ()

main : () -> () ! {Http, Console, Async}
main () =
  route GET "/users/:id" \req ->
    id <- parseId req.params.id
    user <- fetchUser id          -- 效应自动追踪
    json user

  route POST "/users" \req ->
    body <- decode req.body
    createUser body
    status 201
```

类型签名即文档:`! {Http, Console, Async}` 精确说明了这个程序能做什么。

---

## 8. 工具链设计

| 工具 | 特性 |
|------|------|
| `lumen build` | 增量编译,内容寻址缓存(类似 Unison) |
| `lumen fmt` | 唯一官方格式化,无配置项 |
| `lumen test` | 基于属性的测试内置,自动生成用例 |
| `lumen repl` | 可回溯时间的调试 REPL |
| 包管理 | 去中心化,按内容哈希寻址,无依赖地狱 |

---

## 9. 与现有语言的差异化

| 特性 | Haskell | OCaml | Elm | **Lumen** |
|------|---------|-------|-----|-----------|
| 副作用模型 | Monad/IO | 直接副作用 | 运行时托管 | **代数效应** |
| 类型标注 | 可选 | 必需(部分) | 可选 | **完全不需要** |
| 空指针 | Maybe | option | Maybe | **编译期消灭** |
| 并发 | STM/多种 | 线程 | 无 | **结构化并发** |
| 线性资源 | Linear Haskell(扩展) | 无 | 无 | **内建** |

---

## 10. 总结

Lumen 的三个杀手级特性:

1. **代数效应作为一等公民** —— 统一了异常、异步、状态、IO 的心智模型
2. **全局类型推断 + GADT** —— 强类型的安全,动态语言的简洁
3. **线性类型资源管理** —— 没有 GC 暂停,也没有手动 free

想深入探讨哪个部分?比如效应系统的形式化语义、类型推断算法(基于 bidirectional + row typing),或者写更多示例代码?
