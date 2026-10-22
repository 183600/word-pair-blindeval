# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 9 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 74.4s | **tokens:** 196/12223(推理 7559) | **finish:** stop

---

# Alma —— 一种以「重写」为一等公民的函数式语言

> **一句话**：Alma 是一个**全函数（total-first）**语言，它把**代数效应、线性类型、行多态**放进 Hindley–Milner 内核，并把**用户可写的重写规则**提升为一等公民——规则既是宏、也是优化器、也是类型层计算、也是求值策略的入口。

设计口号：**默认全、可证全；效应是方程；线性是纪律；重写是权力。**

---

## 0. 设计目标（为什么不是又一个 Haskell / OCaml / Idris）

| # | 目标 | 具体做法 |
|---|---|---|
| 1 | 全函数优先 | 非法/不安全函数不能通过类型检查；`unsafe` 会引入隐式 `partial` 效应，必须被显式「消解」 |
| 2 | 效应可组合、可局部 | 代数效应 + 深/浅 handler，效应行随函数流动而非被单子固定 |
| 3 | 资源必须可见 | 线性类型（`!`）标注不可复制/必须恰好用一次的资源（文件、锁、随机源、DOM 节点） |
| 4 | 抽象能力而非绕过封装 | 行多态记录 = **能力（capability）**，取代全局可变状态与 unsafe FFI |
| 5 | **元编程不是「另一个世界」** | `rule` 声明的重写规则同时服务于：宏展开、编译期求值、类型层规约、优化器 |

第 5 点是 Alma 的核心创新：Haskell 的 `deriving`/TH、OCaml 的 PPX、Rust 的宏，各自是一套独立且受限的机制；在 Alma 里它们**只是同一种东西**——重写规则。

---

## 1. 记号约定

```alma
-- 行注释 {-块注释 -}
A -> B          函数类型          A !{ ... }   效应行（! 前缀区分于记录行）
{ x : Int | r } 开放记录行          forall a. 全称量化
data T a = ... 代数数据类型        type A = ...  类型别名/新类型
```

**语法风格**：缩进敏感（2 空格），类 Haskell 但更「命令式直观」：

```alma
main : ()
main = printLn "hello"
```

---

## 2. 词法与文法（节选 EBNF）

```ebnf
Program     = Decl*
Decl        = Module | Data | Rule | Signature | Bind | Instance
Bind        = Pat+ "=" Expr              -- 多子句模式匹配
Data = "data" ConName Params "=" Con+
Con = ConName Atoms | "(" ConName "{" Field,* "}" ")"
Rule        = "rule" Pat "=" Expr        -- 一等公民重写规则
Expr        = Lambda | Case | If | Do | Handle | Let | App | Lit | Var
Handle      = "deep"? "handle" Expr "with" HandlerClause+
HandlerClause = OpName Pats "=>" Expr
```

`Let/Do/Handle/Match/If/Case` 之间存在固定优先级（`$` 最低、`app` 最高），因此**不需要用户记8 个运算符优先级**。

---

## 3. 内核语言

### 3.1 数据类型与记录

```alma
data Shape  = Circle Float
  | Rect { w : Float, h : Float }

area : Shape -> Float
area s = match s with
  Circle r      -> pi * r * r
  Rect { w, h } -> w * h
```

记录是**行多态**的，这带来「按需能力」：

```alma
type Env = { lookup : String -> Value,   -- 必需能力
             clock : () -> Int,           -- 可选能力
             | r }                        -- 剩余字段（未知）
```

### 3.2 模式匹配是完备检查的（且给出修复建议）

```alma
bad : List a -> String
bad xs = match xs with
  [] -> "empty"
-- 错误：non-exhaustive patterns
--   缺少子句：  (y : ys)
--   提示：      bad (y : ys) = ...
--   或显式：    _ -> unreachable "bad: caught"
```

`unreachable` 是安全出口：它要求当前函数**上下文穷尽性成立**，由类型/覆盖检查器验证，而不是靠程序员祈祷。

### 3.3 终止性

- 对 ADT 参数做**结构递归**的函数：自动终止（大小变换检查）。
- 对 `Int`/`[a]` 递归必须显式声明：

```alma
collatz : Int -> Int
collatz n = inductive (if n mod 2 == 0 then collatz (n/2) else collatz (3n+1))

gamma : Int -> Float
gamma n = unsafe (if n <= 0 then error "bad" else gamma (n-1))   -- 逃逸口
```

---

## 4. 代数效应

### 4.1 效应行

```alma
readFile : String -> String !{ io : { read : Path -> String } }
runMain  : () -> () !{ io : IoOps, exit : Int -> () }
```

### 4.2 Handler

```alma
safeDiv : Int -> Int -> Int !{ throw : String }
safeDiv a b = if b == 0 then throw "division by zero" else pure (a `div` b)

demo : Int !{ throw : String }
demo = safeDiv10 0

-- 深 handler（默认）：处理结果继续被同一 handler 处理
safeDiv2 = handle demo with
  throw e -> -1
```

handler 子句可用的操作：

| 形式 | 语义 |
|---|---|
| `op k` | 得到续延 `k` |
| `op as k` | 得到操作参数 `as` 与续延 `k` |
| `pure x` | 截获返回值 |
| `resume` | 用原操作参数恢复（浅 handler 语义） |
| `retry` | 回到 handler 重试（用于非确定性/回溯） |
| `resumeMany k xs` | 对 `xs` 每个元素运行 `k`，展平收集结果 |
| `abort` | 提前终止整个计算 |

`deep handle`（递归 resume）与 `handle`（只 resume 一次）区分清楚——这是 OCaml 效应处理器最常踩的坑，Alma 把它做成**必须写的关键字**。

### 4.3 `do` 记法就是 handler 的语法糖

```alma
main = do
  x <- readLine -- do 展开为 handle + bindE
  y <- if x == "" then throw "empty" else pure x
  printLn y
```

### 4.4 三个完整可运行的例子

**(a) 超时——展示「消除效应」**

```alma
--效应：now : () -> Int, after : Int -> ()
withTimeout : Int -> a !{ now : () -> Int, after : Int -> () } -> Maybe a
withTimeout n m = handle m with
  now k      -> resume k n              -- 冻结时间
  after _ k  -> resume k ()             -- 跳过所有延时
  pure x     -> pure (Some x)
```

**(b) 非确定性与解析器——`resumeMany` 就是 `bind` + `Alternative`**

```alma
-- 效应：pick : [u] -> v   （"给出这些 u 中的任意一个，并继续"）
runP : a !{ pick : [u] -> v } -> [a]
runP m = handle m with
  pick cs k -> resumeMany k cs

bindE : a !{ pick : [u] -> v } -> (a -> ![w]) -> ![w]
bindE m f = handle m with
  pick cs k -> resumeMany (\u -> wrap (f (k u))) cs

-- 于是：
type P a = a !{ pick : [u] -> v }

char  : Char -> P Char
char c = pick [c]

oneOf : [Char] -> P Char
oneOf cs = pick cs

sat : (Char -> Bool) -> Char -> P Char
sat p c = if p c then char c else failP

infixl 0 |>
(|>) : P a -> P a -> P a
m |> n = bindE m (\_ -> n)             -- 只取第一个结果

digits : P [Char]
digits = many (sat isDigit `orElse` many (char ' ')) `andThenMany` ...
```

整个非确定性运行时的语义，在上面三行里写完了——这正是我们想要的：**代数效应让「monad = handler」成为可书写的事实，而不是宏。**

**(c) 线性资源 + 异常安全**

```alma
data File !Fd = { osFd : Fd, path : String } -- !Fd：内部资源线性

bracket : a -> (a -> b) -> (a -> c -> d) -> d !{ io : IoOps }
bracket acquire release body =
  handle body acquire with
    pure x   -> release acquire x; pure x
    throw e  -> release acquire e; throw e other o k -> resume -- 其它效应照常传播

withFile : String -> ((File !Fd) -> a) -> a !{ io : IoOps }
withFile p k = bracket (openFile p) closeFile k
```

`bracket` 是**普通的多态函数**，不是语言内建——因为效应是行，所以「异常安全的资源管理」无需特例语法。

---

## 5. 线性 / 仿射类型

- `T` —— 可复制、可丢弃。
- `T !n` —— **必须恰好使用 `n` 次**（Linear Haskell 风格的用法检查）。
- `T ?` —— 仿射：至多一次，丢弃必须显式 `drop t`。

```alma
dup : File !Fd -> (File !Fd, File !Fd)     -- 错误：线性值被复制
use : File !Fd -> Int -- 错误：线性参数未被使用
ok  : File !Fd -> File !Fd -> Int          -- 合法：两者各用一次
giveUp : File !Fd -> IntgiveUp f = 0 `seq` drop f; 0
```

类型检查器用法规则（`Γ ⊢ e : A^u`，`u ∈ {0,1}`，在 Gamma/Lambda 的**系数环 Z/nZ** 上做约束求解），配合注解消除歧义。`Int` 与 `String` 默认为 `Copyable`，用户数据类型默认**仿射**——这是重要的安全默认值：新建类型默认「拥有资源」。

---

## 6. 行多态记录 = 能力（旗舰示例）

一个解释器：没有全局环境，没有 `unsafe`，只有「传进来的那部分世界」。

```alma
type Value = Num Int | Fun (Value -> Value) | Prim String

data Expr = Lit Int | Var String | Call Expr Expr | Lam String Expr

eval : { lookup : String -> Value, clock : () -> Int | r }
 -> Expr -> Value !{ throw : String }
eval env e = match e with
  Lit n       -> Num n
  Var x       -> handle env.lookup x with
                  missing => throw ("unbound: " ++ x)
  Lam x b     -> Fun (\a -> eval env b)     -- 部分应用：闭包捕获能力
  Call f a    -> handle applyF (eval env f) (eval env a) with
                  Num k -> Num k
                  Prim s -> Num (stoi s)
                  Fun g  -> g a              -- 这里类型检查失败：g 的能力行 ⊉ env
```

最后一行给出错误：

```
错误：无法应用 g
  g : Value -> Value !{ ... | r1 }
  需要：        r2 ⊇ { lookup, clock }        -- 闭包要求的能力不在 r1 中
提示：闭包已捕获 { lookup }，若要获得 clock，请在构造 Lam 时显式传入
```

**这就是本语言对「全局可变状态」的回答**：能力以行的方式被捕获、被检查、被最小化。

---

## 7. 重写规则：Alma 的真正卖点

### 7.1 语法与一等性

```alma
rule id x            = x
rule (f `compose` g) x = f (g x)
rule (x : xs) ++ ys   = x : (xs ++ ys)
rule [] ++ ys         = ys
```

一个 `rule` 的值类型是 `Rule`，可以放进列表、传给函数、被 `rewrite` 组合：

```alma
optimizations : [Rule]
optimizations = [rule (\x -> x), rule (x * 0 = 0)]

rewrite : [Rule] -> Expr -> Expr
```

### 7.2 四种用途，同一种语法

**(1) 宏 / 领域专用语言（编译期求值）**

```alma
matrix : Int -> Int -> Float
matrix m n = $( [ expr | i <- range m, j <- range n ] )   -- $[] 内嵌宏，编译期展开
```

**(2) 类型层计算（不引入依赖类型内核）**

```alma
rule (Elem a [a])        = True
rule (Elem a (b : _))    = and (Eq a b) (Elem a _)
rule (Eq a a)            = True
rule (Eq a b)            = False

contains : [Int] -> Int -> Bool
contains xs x = $( Elem x xs )            -- 编译期决定，运行时零成本
```

**(3) 优化器与规则重写**

```alma
rule (x : xs) |> f = f x : (xs |> f)    -- 列表 map 的增量融合
rule (foldl f z xs) where noStrict f = fuseLoop ...
```

**(4) 求值策略本身可被用户改写**

```alma
default strictness = byValue          -- 全语言默认严格lazy id x = x
rule (force (delay e)) = e            -- 打开惰性：把 byValue 全局换成 byNeed
```

「call-by-value / call-by-need / head-call」在 Alma 里不是语言的三个选项，而是**一组可被用户继承/覆盖的规则**。你甚至可以为一个特定函数写求值策略：

```alma
strict parseTree s = s `seq` ... -- 强制参数以获得栈安全
```

### 7.3 规则的可信性

- 所有规则默认检查**终止性**（大小变换 + 词典序），因此 `normalize` 一定终止。
- `rule` 是**等式**：模块内可以 `rewrite` 任意表达式来利用它们，语义保持由「规则可判定的正确性」保证。
- 关键函数可标注 `checked` —— 若所有调用点都在编译期被规约完，运行时版本被类型检查器标记为「不可达」，省掉一个函数闭包。

---

## 8. 依赖类型作为「库」而非「内核」

内核保持 HM + 行 + 线性（可推断、可扩展），精化类型/证明项由规则宏提供：

```alma
type IsJust : * -> *
rule (IsJust (Just _)) = Unit
rule (IsJust Nothing)   = Void

headOr : List a -> Maybe a
headOr xs = refine xs

head xs = match xs with
  (x : _) -> x
  []      -> fromJust (headOr xs)      -- 需要 IsJust xs 的证据；检查器要求
```

好处：核心小、实现可控；代价：精化检查依赖宏展开能力（我们正在做的正是这件事），早期版本先提供 `inductive` + GADT-lite。

---

## 9. 其它语言特性（简表）

```alma
-- 具名参数 / 管道（内建运算符，非库）
data Point = { x, y : Float }
dist p q = (p - q) |> norm2 -- 管道绑定最左的「洞」

-- 一等模块：模块 = 记录 = 带约束的行
type Monad m = { return : a -> m a, bind : (m a -> (a -> m b) -> m b) | r }
instance Monad List where
  return x = [x]
  bind xs f = xs |> map f |> concat

-- 重载通过字典 + given 子句，无类型类层级
sortBy :: Ord a => (a -> a -> Ordering) -> [a] -> [a]

-- 记录字面量与更新（类型检查器保证更新的字段存在）
p1 = { x = 0.0, y = 0.0 }
p2 = p1 { x = 1.0 }

-- 精确报错（类型）
bad = if true then 1 else "s"
-- 类型错误：if 的分支类型不一致
--   Int vs String
--   提示：使用 sum type data Ior a b = Left a | Right b

-- 渐进式逃生口
bad2 = @unchecked (head [])
```

`@unchecked` / `@unsafe` 在语言层面可见、可 grep、可在 CI 中被统计报告——而不是像 C那样散落在系统里。

---

## 10. 实现路线

| 层 | 方案 |
|---|---|
| 解析 | 缩进敏感 Pratt 解析器，产出带 span 的 CST；错误信息带源码切片与「你要的是不是 …」建议 |
| 类型检查 | HM + 行多态（Unification by rows, Leijen 风格）+ 线性用法检查（Linear Haskell 的 Z/2 系数环）+ 效应行 → 残余 monad 的**自由单子**重写（ZINC 方案） |
| 求值 | **Glue 解释器**：把 CBV 重写语义编译到闭包 + 显式栈，保证 handler 的 `resume` 有正确语义且栈安全 |
| 编译 | 重写内核 → 后端闭包/CPS → LLVM；优化器本身用重写规则实现（自举） |
| 宏 | 规则集合按模块分层，作用域化；展开结果做卫生处理（闭包捕获而非文本替换） |
| 终止性 | 大小变换终止检查器，失败时报出「请加 inductive 注解或给出下降函数」 |
| REPL | 逐模块增量类型检查；`:type`, `:rules`, `:normalize e` 直接暴露重写引擎 |

**自举目标**：Alma 的编译器与标准库用 Alma 自身实现（第一阶段用 Rust + 一层薄宏，后续换成规则）。

---

## 11. 完整的「有说服力」示例：不可变 Set（用到线性与重写）

```alma
data Set a = Empty | Node !Int !(Set a) !(Set a)   -- 元素线性：禁止重复

insert : Ord a => a -> Set a -> Set a
insert x s = rewrite (insertR x Empty s)

rule (insertR x Empty Empty)       = Node x Empty Empty
rule (insertR x Empty (Node y l r)) = if x < y then Node y (insertR x Empty l) r
                                    else if x > y then Node y l (insertR x Empty r)
                                    else Node y l r
rule (insertR x (Node y l r) Empty) = ... -- 省略：线性版的结构递归规则
```

对比现实：上面这个数据结构在 Haskell 里需要 `Map` + 类型类 +严格性标注；在这里「元素不可复制」是**类型层的规格说明**，而插入的展开是**一条用户可读的等式**。

---

## 12. 代价与已知问题（诚实的部分）

1. **规则系统会失控**：Alma 面临 ML/Haskell 系统里所有宏系统的经典问题（阶段分离、捕获、编译期爆炸）。缓解：`rule` 必须在编译期终止 + 展开有 fuel 上限 + 报错指出「哪条规则导致展开10⁷ 次」。
2. **线性类型 + 多态的交互**：`(forall a. a !a -> a !a)` 这类高阶线性函数需要 `let !` 强制标注，初期推断会给出较多提示。
3. **handler 性能**：`resumeMany` / 浅 handler 需要续延复制，成本高；编译器对「可静态消除」的效应做闭包内联。
4. **终止性检查不可判定**：需要 `inductive` 标注与少数 `unsafe` 逃逸口；我们认为这比 OCaml/Haskell 里的「沉默的非终止」好，但仍是负担。
5. **依赖类型是宏给的**：宏展开期做证明检查，若展开不可判定则要求用户显式提供证据项——体验不如真正的 dependently-typed 内核。

---

## 13. 一句话总结

> 如果说 Haskell 让「程序 = 值 → 值」的函数式内核配上单子代数成为主流，
> 那么 Alma 想做的是：**把「程序 = 值 → 值」+「等式 =变换」合到同一条语义的流水线上**——
> 效应是等式的左侧，重写是等式的求解器，类型是等式的类型，线性是等式的资源纪律。
> 元编程不再是语言外的特权，而是语言内的一种**可被检查、可被组合、可被类型化的普通表达**。
