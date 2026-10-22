# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 4 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 49.8s | **tokens:** 196/7573(推理 3357) | **finish:** stop

---

# Coda —— 一种以效应为核心、以模式为入口的函数式语言

> 命名自音乐术语 *coda*（尾声），一语双关：它是"曲子的结束"，也是"代码经过组合后落到机器上的最终结果"。
> 编译器同名：`coda build`、`coda repl`、`coda check`。

---

## 一、设计目标（决定了后面的一切取舍）

| # | 目标 | 含义 |
|---|---|---|
| G1 | 效应即语法 | 所有副作用都出现在**类型**里，且由**处理器（handler）**在语言层面消除，而不是靠一堆 Monad |
| G2 | 一处模式，处处控制流 | `match`、`let`、函数定义、handler 分支共享同一套模式语言 + guard + 视图 |
| G3 | 推断优先 | 99% 的程序零类型标注；效应行（effect row）自动推断并泛化 |
| G4 | 资源不可泄漏 | 线性（linear）类型 + 非词法生命周期：文件、socket、锁在类型层面不能被复制或遗忘 |
| G5 | 默认安全 | 穷尽性检查、终止性检查、`shift/reset` 隔离控制流、悬垂引用不可能出现 |
| G6 | 可渐进化 | 支持 `?T` 动态逃逸（gradual typing），但保证 soundness |

**刻意不做的事**：不做隐式 `do` 记号的类型类魔法（GHC 的 `Monad` 约束问题），不做多态递归/更高级类型（除非作为实验特性），不做纯理论驱动的复杂度。

---

## 二、类型系统总览

```
T ::= Int | Float | Bool | String | Unit | ?T                       -- 基础类型
    | A -> B            -- 纯函数（等价于 A ~> {} -> B）
    | A ~> e -> B       -- 效应函数：e 是效应行
    | (A, B) | [A] | { l: T, ..r }   -- 元组 / 列表 / 行多态记录
    | A | B | type 参数（kind = Type）  -- 代数数据类型
    | forall a. T | forall a <: C. T   -- 参数多态 + 类约束
    | linear T | affine T             -- 线性/仿射修饰
```

效应行（effect row）：

```
e ::= {}                          -- 纯
    | E | r                       -- 开放行：E 是闭效应，r 是行尾变量
    | {State s, Throw String, ..r} -- 具名 + 形参的开放行
```

关键点：**效应多态是 predicative 的**。只有不涉及函数返回值的约束才会被泛化，从而消灭了 GHC 的 `Monadic Restriction`，也顺带消灭了 "`return` 能不能多态"这个几十年的语义争论（Coda 的答案是：效应由 handler 决定，与 `return` 无关）。

---

## 三、语法骨架（Coddle 风格）

```coda
-- 单行注释
--| 文档注释

module Geometry

import Data.List as L -- 限定导入
open Data.Maybe -- 无限定导入

type Shape
  | Circle of Float
  | Rect   of { w: Float, h: Float }

area : Shape -> Float
area s = match s with
  | Circle r       -> pi * r * r
  | Rect { w, h }  -> w * h

-- 三种等价写法（无优先级差异，只按上下文消歧）
f x y = x + y
f  = \x y -> x + y
f  = fun x y -> x + y
```

管道与块：

```coda
[3,1,2]
  |> L.sort -- 显式管道：好读、可组合、可优化
  |> L.map (fun x -> x * 2)
```

```
let| fib0 = 0           -- let 绑定带 guard | fib 1 = 1
    | fib n | n > 1      = fib (n-1) + fib (n-2)
```

---

## 四、标志性特性之一：代数效应 + 双向效应推断

### 4.1 语法

效应通过 `effect E of T` 声明为**信号（signal）**，通过 `perform` 发射：

```coda
effect State of { Get : Unit -> s | Put : s -> Unit }
effect Ask   of (Char -> Bool)
effect Fail  of String

type Parser[a] = List[Char] ~> { Ask, Fail } -> a
```

处理器（handler）：

```coda
-- 深处理器：把控制权向上传播一层，同时给递归深度设上限
parse : Parser[a] -> a
parse p = handle
    -- 显式的递归护栏（Deep handler 是库提供的，不写也行）
  | effect Ask pred k   -> resume k (lookahead pred)
  | effect Fail msg k   -> fail ("parse: " ++ msg)
  | effect Deep n k -> if n > 10_000 then fail "budget" else resume k (n + 1)
```

`handle e with | effect Op arg k -> ...` 中的三个槽位含义固定、位置固定：
`Op` 效应名、`arg` 操作数、`k` 续延。**这行模式就是整个语言的"for-each + try/catch +状态"的统一体**。

### 4.2 为什么这比 Monadic 风格好

```coda
-- Koka 式的深层处理器让"递归回溯"变成两行库代码，而不是读者必须理解的 reify/reflectbacktrack : Parser[a] ~> {Fail} -> a
backtrack p = handle  | effect Fail _ k -> backtrack (resume k)
```

而同样的程序在 Haskell 里需要读者在 `Alternative`、`MonadPlus`、`Control.Monad.Catch` 之间来回跳。Coda 的选择/状态/异常/续延是**同一种东西的不同实例**，而不是四种不同的库概念。

### 4.3 续延是一等值

```coda
effect Shift of { Yield : Int -> Unit; Resume : () -> Int }

tick : Int -> () ~> { Shift, State Int } -> Int
tick n = handle with
  | effect Yield i k -> { perform (Yield i); perform (Put (get + 1)) ; resume k }
```

`reset/shift` 由 `handle` **内建**，无需 `delimited-continuation` 库；handler 捕获的续延与捕获时的词法环境绑定（capture-concurrent、栈安全、可跨线程不可化）。

---

## 五、标志性特性之二：线性类型 + 非词法生命周期

```coda
linear type File
linear type Mutex

-- 线性值恰好被消费一次
readAll : File -> String -- 消费掉了：之后 f 不可用（类型错误）

-- 仿射：至多一次
affine log : (String -> Unit)      -- 可以丢弃，但不能重复调用

withFile : String -> (File ~> {IO} -> a) -> a
withFile path body =
  let! f = open path -- 取得所有权（独占借用）
  let! s = readAll f             -- readAll 消费 f
  close f -- 关闭
  pure s
```

Coda 的定位与 Rust 不同：线性的是**值**（句柄、能力、锁、GPU 缓冲区），而借用检查是**类型推断出来的**。用户几乎不写 `linear` 标注（由 `type` 声明自动传播），只在库边界出现。

它和效应行正交且可组合：`File ~> {IO} -> a` 是"消耗一个资源且可能做 IO"。

---

## 六、标志性特性之三：卫生宏 + 分阶段（staged）编译期计算

```coda
--声明一个宏（函数是编译期函数）
macro json_field name =
  quote
    {~~~name : String -> Int,
~~~name = fun s -> match s with | #"{" s = s' }" -> { ... }   -- 内建正则 + 模式模板 }

-- 生成代码
record_of_fields "id" "name" "age" |> expand
```

要点：
1. **卫生重命名**由编译器保证（与 Rust `macro_rules!` / Racket 同级）。
2. `quote ...~~~x` 是**带洞的项**，不是字符串模板 ⇒ 不存在 `concat` 引号地狱。
3. 宏在类型检查之后展开（语法阶段独立），可访问类型信息：`| defn(n: Int)` 只在 `Int` 参数处生效。
4. 编译期求值是**受控**的：宏体内不能做 IO，但可以做模式匹配、搜索、单位换算、SQL/正则/协议代码生成。

```coda
-- 编译期求解线性方程组，生成状态转移表
comptime coeffs =
  let sol = solve_linear coeffs in
  emit [ "| S x = " ++ show sol | i <- indices ]
```

---

## 七、其他关键决策

**模式即 API**
- 所有 `match` 强制穷尽；缺分支给出**具体的**反例（"此路径覆盖 `Some` 但漏掉 `None`"）。
- 视图模式 `| n :: Nat` 产生可选失败，需要显式写 `| _ -> fallback`，**失败不会静默**。
- 矩阵编译（决策树），首个匹配分支按源码顺序命中。

**求值策略：默认严格**
```coda
lazy xs = 1 :: lazy [Int]     -- 显式 thunk，需要 lazy 标注
```
理由：严格基线让预测的复杂度成为可承诺的性质；惰性是标注出来的局部优化，而不是全语言的语义黑洞。内部仍然用 call-by-need + thunk 更新（coercion），与 ML 的 `lazy` 一致。

**终止性检查**
基于 size-change / 结构递归，对递归函数签发"下降性证明"。`Deep` handler 提供了打破它的显式出口 ⇒ 惰性、无限列表、对流式需求的封装都能在**有名字的**地方通过检查。

**模块是一等公民**
```coda
module type Comparable = { compare : (self, Self) -> Int }

instance Comparable Shape = { compare = ... } -- 形如记录字面量，no-implicit-param
fun (<?>) : [a] -> (a -> Bool) -> [a]            -- 约束即参数，无歧义
```
实例解析是带回溯的确定性搜索（同约束多处匹配 = **coherence 错误**，而非"最后一个赢"）。

**渐进类型**
```coda
let x : ?T = JSON.parse raw   -- 动态逃逸，只在这里不安全
cast::<Shape>(x)              -- 显式边界：运行时检查，sound```

---

## 八、完整示例：一个带资源与计数的解释器

```coda
effect Counter of { Tick : Unit -> Unit }
effect Bail of String

type Expr
  | Num of Int
  | Add of Expr * Expr
  | Let of String * Expr * Expr
  | Load  of String            -- 打开并读一个文件（线性资源）

type Env = { vars : { ..r }, files : [String], ..s }

eval : Expr ~> { Counter, Bail, Throw String, IO } -> Int
eval e =
  handle    match e with
    | Num n        -> n
    | Add (a, b)   -> eval a + eval b
    | Let (x, a, b)-> let v = eval a in eval b { env = (get env).vars + (x ↦ v) }
    | Load p       -> perform (Tick); let! fh = open p
                      let s = readAll fh; close fh
                      perform (Bail ("imported: " ++ s))
  with
  | effect Tick k         -> put (get + 1); resume k
  | effect Bail s k       -> perform (Throw s)          -- 局部 handler 把 Bail 转成异常
  | effect Throw s k      -> panic s
```

- `eval` 的类型标注**只在签名处**写一次（因为顶层绑定会泛化效应行，内部零标注）。
- `Bail` → `Throw` 的转换发生在局部 handler，类型系统保证：`eval` 对外只承诺 `Throw`。
- 上面 5 个 handler 分支就是普通模式，编译器把它编译成**状态机**（defunctionalization），没有闭包分配。

运行：

```coda
main =
  let r = handle (runCatching (eval prog))
             with | effect Counter n k -> { print "ticks =", n; resume k }
  match r with | Ok v  -> print v
               | Err e -> print "error:"; print e
```

---

## 九、类型检查算法（骨架）

**双向 + 行多态 unification**

1. **推断**：Hindley–Milner 泛化，但泛化的是 `(类型变量, 效应行变量, 类字典变量)` 三元组；谓词化判断为「不涉及更高阶下文的变量」。
2. **行的多态子类型**：`{e | r} ≤ {E, ..r'}` 通过行变量的重命名实现。
3. **子归约**：`A ~> {E | r} -> B` 在 handler 分支中消去 `E`；残留的行尾变量被"深化"（deepened）为顶层 handler 的行——这正是深层 handler 的类型规则。
4. **检查**：只对 `->`、`~>`、`:>`显式标注位置做检查，其余由推断填出，再**精化**（refinement）：
   - 穷尽性：模式矩阵覆盖分析 + GADT 蕴含检查；
   - 终止性：size-change 图；
   - 线性性：值流图 + NLL 借用分析；
   - 效应纯度：`e = {}` 时拒绝一切 `perform`。
5. **精化到 Core**（`forall` + `effect` 抽象显式化），随后做效应擦除：`{} ~>` 的节点编译为普通 MLIR SSA。

**典型错误信息（这是语言设计的重点，不是附注）**

```
coda: 内部效应泄漏 (effect leak) — src/eval.coda:18:3

  eval : Expr ~> { Counter, Bail, Throw String, IO } -> Int
 ^^^^^ 泄漏  `Bail` 在 handle 的 `Throw` 分支被消费，但它同时出现在
  函数体 `eval a + eval b` 之后的续延中（第 18 行的局部 handler
  无法捕获已被 `handle` 包住的调用）。

  建议：把行中的 `Bail` 改为 `Ask`，或将该调用移到 handler 之外：
 | effect Ask s k -> throw (Bail s); resume k
```

对比"Monad transformer stack 不匹配"这类经典300 行报错，Coda 的错误信息必须同时做到：**指出泄漏的效应、指出泄漏的位置、给出可粘贴的修复**。

---

## 十、编译管线

```
 源码 ──宏展开(卫生, 按需展开)──▶ Core(显式 forall/effect)
      ──双向类型检查+精化──▶ 显式效应标注的 Core
      ──handler 去语法(sugar removal: 深 handler → 浅 handler + 局部状态)──▶
      ──defunctionalize──▶ 状态机 ──▶ MLIR (SSA)
      ──线性性检查/NLL 借用 ──▶ 区域 + 所有权 IR      ──effect erasure ({}~> → 纯值) ──▶
   ┌─── 解释后端（教学/JIT）           │
   └─── LLVM/Cranelift 后端：region-based 分代 GC + 可增长栈 + 内建 effect handler 缓存 +续延堆（常驻 segment）
```

后端的两个硬性指标：CPS/handler 状态机分配**零闭包**（栈上可复用）；续延对象使用独立的不移动（pinned）区域，使 `shift/resume` 在跨线程 resume 时不需要引用计数。

---

## 十一、与现有语言对比

| 维度 | Haskell | OCaml | Scala 3 | Koka | Effekt | **Coda** |
|---|---|---|---|---|---|---|
| 效应表达 | 类型类字典 | 编码 | 编码 | 内建 | 内建 | **内建 + 行多态推断** |
| 效应多态 | Monadic Restriction | — | — | 隐式泛化 | 隐式泛化 | **predicative，自动** |
| 模式统一 | 仅 case/let | + 少量模块级 | 抽取子 | 无视图 | 有限 | **match/let/宏/handler 共享** |
| 线性 | 提案阶段 | 提案阶段 | 无 | 无 | ✔ 全程序线性 | **值线性 + NLL 借用** |
| 编译期宏 | CPP + Template Haskell | PPX | 宏/引用宏 | 无 | 无 | **带洞的卫生项 + 类型信息** |
| 求值 | 惰性 | 严格 | 严格 | 严格 | 严格 | **严格默认 + 显式 lazy** |
| 渐进类型 | 无 | 无 | 无 | 无 | 无 | **✔ sound 的 `?T`** |

---

## 十二、已知风险与诚实评估

1. **效应行 + 类约束 + 线性，三套多态共存** ⇒ 推断会出复杂病。缓解：推断器只实现 predicative 全序子片段，`{ effect ... }` 行的推断需要用户偶尔写一次标注。
2. **handler 糖去除后的类型规则膨胀**（深 handler → 浅 handler 会把行拆成两份）。缓解：深 handler 只允许在顶层/模块级，避免隐式深层组合。
3. **卫生宏会诱导出 2000 行的宏库**（Lisp 老问题）。缓解：默认限制宏的重复展开预算（类似 Rust 的 recursion limit），并提供 `unquote` 的展开可视化。
4. **终止性检查的可用性**：size-change 对高阶函数不精确 ⇒ 提供 `unbounded` 显式逃逸口（像 `unsafe` 一样刺眼）。
5. **生态成本**：没有 GHC 的30 年积累。缓解：先做 JSON/正则/解析器/并发四件套的官方库，把语言特色（handler写解析器、线性写文件管道）做成杀手锏示例。

---

## 十三、一页纸总结

> **Coda 是一种"以代数效应为唯一副作用机制、以模式匹配为唯一控制流"的静态函数式语言。**
>
> 它的三条创新点是：
> 1. **统一 handler 语法** —— `handle e with | effect Op arg k -> ...`，让异常、状态、回溯、续延、协程、解析共享同一个可被类型推断的模式；
> 2. **值线性 + 借用推断** —— 资源安全不靠 GC，也不靠用户写 `linear` 标注；
> 3. **带洞的卫生宏** —— 编译期编程是"生成被类型检查的项"，而不是"拼接字符串"。
>
> 一句话记忆：`match` 是 Coda 的 `if`，`handle` 是 Coda 的 `monad`，`linear` 是 Coda 的 `RAII`，`quote` 是 Coda 的宏 —— 而它们全部共享同一套模式语言。
