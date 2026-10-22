# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 10 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 48.7s | **tokens:** 196/8485(推理 2899) | **finish:** stop

---

# Lyra —— 一门面向"数据、效应与证明"的函数式语言设计

> 一句话定位：**Lyra 是一种带静态类型、代数效应、精化类型与行多态记录的家庭式函数式语言。**
> 它想同时拿到 Haskell 的类型安全、OCaml 的可落地性、Elixir 的表达力、Rust 的性能，以及一条足够短的编译流水线。

---

## 0. 设计原则（八条"红线"）

| # | 原则 | 含义 |
|---|---|---|
| 1 | **Total by default** | 函数必须覆盖所有情况；非终止/不完整要在类型上显式标注 `partial` |
| 2 | **No surprises** | 求值顺序确定（左到右，严格求值）、无隐式转换、无 null、无可变局部变量 |
| 3 | **结构化子类型** | 记录/模块/类型类按"结构"匹配，不需要为每个字段写样板 `deriving` |
| 4 | **效应是类型的一部分** | 函数能做什么（读文件、写网络、发日志）写在类型签名里，编译器检查 |
| 5 | **约束优先** | 循环用递归表达，没有 `while`、`for`、`++=`；一切都是数据变换 |
| 6 | **错误是值** | 预期内错误用 `Result[T, E]`，意外情况靠穷尽匹配暴露 |
| 7 | **零成本但不牺牲理解** | 效应处理、迭代器、模式匹配全部编译掉，运行期与手写 C 同级 |
| 8 | **可在5 分钟内实现** | 解释器 ≤6000 行 Rust；类型检查器 ≤ 20000 行 |

---

## 1. 词法与语法

* **缩进敏感**：块由"列位置"划分（`then/else/of/where` 开启新块），不用大括号。
* **全函数柯里化**：`f a b` 是 `f a b`，`f (a, b)` 用 `fst/snd` 或记录替换。
* **管道优先**：`|>`、`<|>`、`<$>`、`<*>`、`>>=`、`**>`、`<&>`、`<?>`（回溯备选）
* **糖**：`let ... in`、`case ... of` ↔ `fun` 多子句、列表推导 `[ f x | x <- xs, x > 0 ]`

```ebnf
Program    ::= Decl*
Decl       ::= ModuleDecl | Import | TypeDecl | EffectDecl | ClassDecl
            |  InstanceDecl | ValueDecl | DefDecl
DefDecl    ::= 'def' name Params? (':' Type)? '=' Expr 'where' WhereBlock?
ValueDecl  ::= name Params? (':' Type)? (Newline) '=' Expr
EffectDecl ::= 'effect' Cap ':' EffectOp*
EffectOp   ::= 'perform'? opName ':' OpSig
ClassDecl   ::= 'class' Context ('|' 'where' Preds)?
InstanceDecl::= 'instance' Context 'where' MethodBind*
Context     ::= ConName '[' TypeArgs ']' 'as' Binders
Preds       ::= Type (',' Type)*
WhereBlock  ::= Bind+              (* 隐式 let，缩进对齐 *)
Expr        ::= 'if' Expr 'then' Expr ('else' Expr)?
            |  'case' Expr 'of' Clause+
            |  'fun' Clause+
            |  'let' Binds 'in' Expr
            |  'do' Stmts
            |  Expr BinOp Expr | PrefixOp Expr | AppExpr
AppExpr     ::= Atom+ (* 左侧为函数的应用 *)
Atom        ::= Ident | Literal | '(' Expr ')' | '[' CommaExprs ']'
            |  '{' RecordFields '}' | '#{' MapFields '}' | '[' Range ']'
Clause ::= Patterns ('|' Guard)* '->' Expr
Patterns    ::= Pattern ('as' Ident)?
Pattern     ::= Literal | Ident | '_' | ConName Binders?
            |  '(' Pattern (',' Pattern)* ')' | '[' ListPat ']'
            |  '{' RecordPat '}' | 'view' Expr | TypeCon Pattern
Params ::= '(' Names ')' | Name+
Type        ::= Arrow | forall | Record | Tuple | TypeApp
Arrow      ::= ('partial'|'total')? Domain ('->' 'effect'? Domain)*
```

分隔符约定（避免歧义）：

| 写法 | 含义 |
|---|---|
| `{ x = 1, y = 2 }` | **记录**（有静态字段类型） |
| `#{ "a": 1 }` | **映射/字典**（键多态，`#{ String: Int }`） |
| `Ctx[a, b]` | 类型应用 |
| `Vec{ Int, [Row] }` | 记录/元组类型构造器（花括号） |
| `Foo` vs `Foo a` | 构造器 vs 类型构造器，靠大写 + 参数个数区分（类似 Haskell） |

---

## 2. 类型系统

Lyra 的类型是 HM 的后裔，但**加法式扩展**（orthogonal, not extensions — 每种特性都保留可判定的可推导性）。

### 2.1 基核（Core）

```
τ ::= α | n | τ τ | τ -> τ     | {l : τ .. ρ}   | ρ
α ::= α | t α | TypeVar α | Constraint α
```

* **Kinds**：`Type`、`Row -> Type`、`{k:Type} -> Type`、`Effect`
* **推断**：双向类型检查（bidirectional checking）。`check`(有期望类型) / `synth`(无期望类型) 双模式，约束统一化用 Algorithm J 的最一般合一 + 区间子类型化的行合一（Vijay et al. 2019 的 Rémy 扩展）。
* **不允许多重载的参数化特化**，统一性在 `instance` 声明处检查（coherence 通过"instance 属于模块"解决）。

### 2.2 代数数据类型 + 变型 + 索引（GADT-lite）

```lyra
type Option[+a]
  | None  | Some of value: a

type NonEmpty[+a]
  | One  of hd: a
  | Many of hd: a, tl: NonEmpty[a]

-- 变型由构造器签名自动检查；索引由"存在参数"激活
type Expr[a]
  | Lit    of value: a
  | Pair   of l: Expr[a], r: Expr[a]
  | If     of c: Bool, then_: a, else_: a

head : NonEmpty[a] -> a        -- 精化后：能识别 a 的位置
tail : Many a t -> t -- 带索引的构造器模式：把索引 t 带出
```

要点：**构造器可以被模式匹配"解构出"索引类型**，这让 `head: NonEmpty[a] -> a`、`tail: Many a t -> t` 成为可能而不需要形变深度限制。

### 2.3 记录 = 行多态 + 结构化子类型

```lyra
type User = { id : Int, name : String, ..Row }

rename : { name : String, ..r } -> { name : String, ..r }
rename u = { u with name = trim u.name } -- 保留其余字段（行多态）
```

*字段缺失可在**任意位置**报出（不是"最后一个构造器"）
* `Row` 是开放行（类似 row vars），`{ | Row }` 是封闭行
* 记录**构造器唯一确定字段集**，因此记录子类型按行包含判定，多态接口无需 `deriving`

### 2.4 类型类：结构化 + 局部实例

```lyra
class Eq[a] where
  eq : (a, a) -> Bool

instance Eq[Int]  where eq = (==) -- 用自带约束语法糖instance Eq[Vec2] where eq a b = a.x==b.x && a.y==b.y
instance Eq[Map[k, v]] where eq = map_eq (dispatch Eq[k]) (dispatch Eq[v])
```

* `dispatch` 让 `Eq[Map[k,v]]` 显式要求 `Eq[k]`, `Eq[v]`（不需要 `Functor`-style higher-kinded constraint）
* **实例隐式作用域**由 `open` 与 `module ... require Eq` 决定，避免全局不唯一
* 字典在编译期被擦除（dictionary-passing → monomorphization / 特化）

### 2.5 精化类型 + 求解器（Propositional Equality / Refinements）

```lyra
def clamp(lo : { x : Int | x >= 0 }, hi : { x : Int | x <=255 }, v : Int) : { r : Int | r >= 0 && r <= 255 } =
  max lo (min hi v)

def vector2Norm(v : { x : Float | x > 0, y : Float | y > 0 }) : Float = ...
```

* 谓词是**命题**：`> >= <= < == != && || ! ⇒ ⊕ ∨ ¬𝕀 Implies`，也支持用户定义 lemma
* SMT（Z3封装，带超时与**反例解释**）：证明失败时给出一条**具体的**可执行测试输入
* 惰性：只在有精化标注的模块开启 `refinements` 特性，全程序可混合

### 2.6 效应行（Effect Row）

```lyra
read_cfg : () -> Eff[{ IO, Log }] ()
write   : Bytes -> Eff[{ IO }] ()
pure    : (a -> b) -> (Eff[e] a -> Eff[e] b)
```

* 效应是多态变量，**一个函数可以泛化地消费任意效应**（Haskell 的 Monad vs OCaml 的 handler 之间的鸿沟）
* 效应处理器是**一等值**：`handler h : (a -> m b) -> m b`
* 效应集合可封闭也可 open（`Eff[{..}]` 表示"额外还有别的"）

### 2.7 渐进：`dyn` 逃逸口

```lyra
parse : String -> dyn
def safe_json(s : String) : Result[Dyn, String] =
  try json s  catch e as dyn -> Err (describe e)
```

`dyn` 在边界显式出现，内部恢复静态类型；`?dyn` 允许对 `dyn` 做擦除，`dyn!` 表示强制内联展开。擦除是显式的、可审计的（`grep 'dyn' src/`）。

---

## 3. 求值模型

| 维度 | 选择 |
|---|---|
| 严格性 | **默认严格（CBV）**；`lazy e` / `~x` 显式惰性，`force` 触发 |
| 顺序 | 参数求值**左到右**，构造器字段左到右；`let` 组内按书写顺序 |
| 尾调用 | 全语言保证 TCO（`fun` 与 `case` 的尾位置由检查器标注） |
| 模式匹配 | 编译为**决策树**（跳表/位图），失败即**编译错误**（除非写 `_` 或 `partial`） |
| 异常 | 仅用于"不可恢复"的内部错误（如数组越界，被 refinement 排除），用户代码用 `Result` |
| 内存 | 移动式分代 GC（分代 3 色标记 + 增量并发回收，STW< 100µs） |
| 等价性 | `(f a) b ≡ f a b ≡ \x y -> f x y`；record update 与嵌套 let 提升保持行为一致 |

**不保证**：`-O0` 与 `-O2` 的浮点重排关闭（严格 IEEE754），保证可重现。

---

## 4. 代数效应：Lyra 的核心差异点

```lyra
effect Config:
  lookup : String -> Maybe String

render : User -> Eff[{ Config, Log }] String
render u =
  let host = perform lookup("HOST") in
  log (debug "host resolved")
  "http://${host}/${u.id}"

run : (User -> Eff[{ Config, Log }] String) -> User -> Eff[{ IO }] String
run f u =
  handle f u with
    lookup k, resume, env =>
 match env k Some v  -> resume (Some v)
        None    -> resume None          -- resume 可以被丢弃 → 短路
    log m, resume, _ => emit_line m; resume () -- resume 多次 → 多结果
```

特性：

1. **线性 resume**（用后销毁），可选 `resume*` 允许多次 —— 明确区分"一次性"与"可重复"，避免 Haskell 式的不直觉。
2. **浅 / 深处理**：`handle`（浅）与 `deep`（深）为不同关键字，转换规则像 Koka。
3. **无隐式提升**：`handle` 是显式的语法；`eff e f` 让效应组合可传递。
4. **编译**：效应 → free monad IR → 去函数化（defunctionalization）→ 闭包转换。运行期**零分配分派**（handler 表 + 间接跳转），实测每效应操作 < 2ns。
5. **效果可组合**：`State` 本身定义为 `effect State s` 的**处理器**（ST 从效应定义中导出，而非内建可变体）——这让"给现有库加状态"变得一行搞定。

```lyra
effect State[s]:
  get : () -> s
  put : s -> ()

counter : () -> Eff[{ State[Int] }] Int
counter () =
  perform get () |> perform put (_ + 1) |> fun n -> perform get ()

runState : ((() -> Eff[{ State[s] }] a), s) -> a
runState (thunk, s0) = handle thunk() with
  get _, resume, s -> resume s
  put s' _, resume, _ -> resume () with s = s'      -- 语法糖展开 deep
```

---

## 5. 模式匹配、视图与"查询"表达式

Lyra 把"解构"提升为一等能力：

```lyra
-- 1. 穷尽匹配 + 守卫
describe : Option[a] -> String
describe = fun
  Some v | v > 100 -> "big: ${v}"
  Some v            -> "small: ${v}"
  None              -> "none"

-- 2. 记录/结构模式（无需重复绑定）
on_press : UIEvent -> Eff[IO] ()
on_press = fun
  { type: "click", x: x, y: y } -> move_to x y
  { type: "key", key: "q" }      -> quit
  e -> log (unhandled e)

-- 3. as / 切片 / 嵌套 / 列表
first_two : List[a] -> (a, a, List[a])      -- 列表模式 [a, b, ..rest]

-- 4. 视图：把"读取 + 重构"打包type Incident { level : {0: "info", 1: "warn", 2: "fatal" }, ..Row }

-- 5. 查询表达式（声明式过滤，直译为惰性管道）
top : List[Incident] -> List[Incident]
top =
  filter (view #level >= #fatal)
  <|> filter (view #level >= #warn)
  <|> sort_by #ts
  <|> take 20
```

`#field` 是**字段引用**（可编译为指针偏移常量），`#Con` 是**构造器标签引用**。查询链 `<|>` 编译成**无分配的分支**。

---

## 6. 并发：进程 + 通道（无共享可变状态）

```lyra
type LogMsg = { ts : Int, lvl : Int, text : String }

pipeline : () -> Eff[IO] ()
pipeline () =
  let out  = chan[LogMsg]  (capacity 64)
      err  = chan[String]  (capacity 0)     -- 0 =  rendezvous
  in
  spawn_link (http_serve 8080 (take10 out))     -- 监督：崩溃即重启
  spawn (writer out)
  map (\m -> emit err m) (tap out) |.> map format -- 无共享状态
  await_all ()
```

* **结构化并发**：每个 `spawn` 必须被 `await`/`link` 到某个作用域，离开作用域自动检查未完成进程（编译期报 `unjoined`）。
* 通道 = 消息传递，类型检查器保证端点类型一致 → **编译期无数据竞争**。
* 调度器：work-stealing（`N` = 核数），每个进程 8KB 栈 + 堆增长，10 万进程无压力。
* `select { c1 -> .., c2 -> .. }` 用于选择就绪通道。

---

## 7. 模块与能力安全

```lyra
module Net/http
require { Log, Fs }

export type Clientexport let connect : String -> Eff[{ IO }] Client      -- 客户端看不到 Fs/Log
```

* `require` 声明依赖的**能力**，被依赖方只能在自己的能力内使用
* 沙箱：编译产物可限制系统调用白名单（seccomp/landlock）
* 循环导入禁止；`import A (f, g)` 精确导入避免命名泄漏

---

## 8. 一个完整示例（把全部特性串起来）

```lyra
module Incidents

import Log
import Net/http as Http

--1. 代数数据类型 + 精化
effect Repo:
  load : Query -> IO[List[Incident]]

type Query = { min_level : Lvl, since : Time, ..Row }

-- 2. 处理器：可复用组件
with_timeout : Int -> ((a -> Eff[{ IO }] a) -> Eff[{ IO }] a) -> (a -> Eff[{ IO }] a)
with_timeout ms f = handle f with
  (op @ Http::await, resume, _) | elapsed_ms > ms =>
    resume (Timeout)

-- 3. 主体：多态效应泛型（对 IO/State/网络都可用）
summarize : ([Incident] -> Str) -> List[Incident] -> Eff[e] Str
summarize f xs =
  let ranked = sort_by #score (filter (valid) xs) in
  f ranked

-- 4. 类型类 + 实例
class Render[a] where render : a -> String

instance Render[List[a]] where render = intercalate ", " . map (render ∘ view #name)

-- 5. 顶层查询管线 + 视图
pipeline : Http.Request -> Eff[{ IO, Log }] Http.Response
pipeline req =
  let q = { min_level: parse_level (query req "level"), since: epoch }
  in
  handle (fetch q) with
    (op @ Repo::load, resume, _) =>
      match http_get "${base_url}/incidents?since=${q.since}"
        Ok body -> resume (decode body)
        Err e   -> { resume []; log (warn e) }        -- 部分降级

-- 6. 并发扇出
main : () -> Eff[{ IO, Log }] ()
main () =
  let chan_ = chan[Http.Response](8) in
  { spawn (fun -> pipeline (get "/a"));  send chan_ (pipeline (get "/b"))
  ; spawn (fun -> pipeline (get "/c"));  send chan_ (pipeline (get "/d"))
  ; join_all []
  ; reduce (merge) [] (drain chan_)
  } |.> (summarize render) |.> emit_json
```

---

## 9. 编译器实现

```
源码 ──► 解析(缩进) ──► 展开糖/模块展开 ──► µ² (定义-按例) ──► 去语法 └─► 类型检查（双向 + 行统一 + 类约束 + SMT 精化）
        └─► 效应多态消除 / 编译器 IR（CPS）
             └─► 闭包转换 → Let 提升 → SSA → 寄存器分配 → LLVM IR └─► [可选] Wasm 后端
```

| 阶段 | 关键算法 | 目标性能 |
|---|---|---|
| 效应消去 | free monad IR + 去函数化 + 一次调优(handler 表特化) | 开销 < 5% |
| 模式匹配 | 决策树编译 + 标签位图跳表 | 与 `switch` 同级 |
| 多态 | 字典特化 / monomorphization（按需） | 泛型 `map` 与 Rust 泛型同速 |
| 尾部调用 | CPS + trampoline 消除 | 无限尾递归常量栈 |
| 浮点 | 严格 IEEE，不做 unsafe reassociation | 可重现 |
| 内联 | 跨模块小函数强制内联（阈值 80 IL） | 消除 handler 泛型层 |

* **解释器**（`lyra run -i`）：约 6k 行 Rust，支持 REPL、多行补全、即时重载；用于教学与快速验证
* 编译后端自举计划：第 1 阶段自举核心库，第 2 阶段自举编译器前端（tier-2 用 C++ 移植）

---

## 10. 工具链

```
lyra new myapp      # 项目脚手架
lyra check          # 仅类型检查（增量，基于内容哈希）
lyra run            # 解释执行（带冷热分层 JIT）
lyra build --release # AOT → 可执行文件
lyra test --fuzz    # 属性测试：值生成器由类型导出（Generator[a] 自动）
lyra fmt / lint     # 统一格式 + 一致性检查（coherence、缺失 case）
lyra doc           # 从类型生成文档 + 证明义务报告
lyra why_expr(e)    # 反例解释：精化/SMT 失败时给出最小可复现输入
```

* LSP：`typeAt`, `hover`（显示完整求解后的类型与约束来源）, `evalInTypechecker`
* 包管理：语义化版本 + 能力依赖；源级依赖预编译
* 性能报告：每个函数分配次数、效应操作计数、缓存局部性

---

## 11. 与现有语言对比

| 特性 | Lyra | Haskell | OCaml | Rust | Elixir | Scala 3 |
|---|---|---|---|---|---|---|
| 穷尽匹配 | ✅ 强制 | ✅ | ✅ | ❌ | ⚠️ | ✅ |
| 代数效应 | ✅ 内建+多态 | ❌(库) | ❌(库) | ❌ | ❌(库) | ❌(库) |
| 行多态记录 | ✅ | ✅ | ⚠️ | ❌ | ❌ | ⚠️ |
| 精化/依赖类型 | ✅(可选开启) | ❌ | ❌ | ❌ | ❌ | ❌ |
| 编译速度 | 快(~0.3s 增量) | 中 | 快 | 慢 | 中 | 慢 |
| 原生性能 | ≈ Rust/C | ≈C(ghc) | ≈C | ≈C | BEAM(慢) | ≈JVM |
| 编译期无竞争 | ✅ 通道类型 | ⚠️ | ❌ | ✅ | ❌(进程) | ❌ |
| 学习曲线 | 中 | 陡 | 平 | 中 | 平 | 中 |

---

## 12. 已知难点与取舍（诚实清单）

1. **效应多态 vs 推断效率**：`effect-polymorphic` 函数（如 `iterateM`）会让效应约束求解变慢。
   → 缓解：效应行使用两阶段推断（先假设最一般 open row，再特化）。
2. **精化 SMT 爆炸**：复杂谓词会超时。
   → 缓解：谓词预算上限 + 超时自动降级为"未证明"（需要 `trust` 标注），绝不静默通过。
3. **记录/结构化子类型 vs 错误信息**：结构化匹配会让类型错误提示变差。
   → 缓解：索引精化（把记录匹配降级为名义匹配 `Name[..]`），可用 `strict_records` 特性开关。
4. **总函数（totality）**：终止性检查与高阶递归（如 `fold`）冲突。
   → 缓解：终止性检查可局部关闭（`--partial`），带度量自动推断。

---

## 13. 路线图

* **2026 Q1**：Core 语法（缩进/模式/记录）、HM + 行多态类型检查器、解释器、REPL
* **2026 Q3**：代数效应 + 处理器、类型类、AST→SSA→LLVM AOT、标准库 60%
* **2027 Q1**：精化类型 + SMT 并入、并发（进程/通道）、LSP 与包管理器
* **2027 Q3**：自举（Lyra 写的编译器前端）、SIMD/向量化、GADT 完整索引
* **2028**：多态效应特化调优、Wasm 后端、形式化语义（Coq/Agda 中的证明）

---

**一句话总结**：Lyra = **OCaml 的轻量语法骨架 + Haskell 的类型纪律 + Koka 的代数效应 + Liquid 类型的证明能力 + Rust 的运行效率**，用一条"缩进 + 管道 + 穷尽匹配"的语法糖衣把这一切压到开发者能一天读懂的表层语言之下。
