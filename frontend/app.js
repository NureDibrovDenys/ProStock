const { useState, useRef, useEffect, useMemo } = React;
const html = htm.bind(React.createElement);

function App() {
    const [objs, setObjs] = useState(INIT);
    const [v, setV] = useState({ k: 22, tx: 70, ty: 50 });
    const [tool, setTool] = useState("select");
    const [sel, setSel] = useState(null);
    const [poly, setPoly] = useState([]);
    const [draft, setDraft] = useState(null);
    const [cur, setCur] = useState([0, 0]);
    const [preset, setPreset] = useState(1);
    const [msg, setMsg] = useState("");
    const [sz, setSz] = useState({ w: 800, h: 500 });
    const svg = useRef(),
        wrap = useRef(),
        drag = useRef(null),
        space = useRef(false),
        S = useRef({});
    S.current = { tool, sel, poly };

    useEffect(() => {
        const ro = new ResizeObserver(([e]) => setSz({ w: e.contentRect.width, h: e.contentRect.height }));
        ro.observe(wrap.current);
        return () => ro.disconnect();
    }, []);
    useEffect(() => {
        const el = svg.current;
        const wh = e => {
            e.preventDefault();
            const r = el.getBoundingClientRect(),
                mx = e.clientX - r.left,
                my = e.clientY - r.top;
            setV(o => {
                const k = Math.min(200, Math.max(4, o.k * Math.exp(-e.deltaY * 0.0015)));
                const wx = (mx - o.tx) / o.k,
                    wy = (my - o.ty) / o.k;
                return { k, tx: mx - wx * k, ty: my - wy * k };
            });
        };
        el.addEventListener("wheel", wh, { passive: false });
        return () => el.removeEventListener("wheel", wh);
    }, []);

    const pick = t => {
        setTool(t);
        setPoly([]);
        setDraft(null);
    };
    const closePoly = () => {
        const p = S.current.poly;
        if (p.length < 3) return;
        setObjs(os => [...os.filter(o => o.t !== "room"), { id: nid(), t: "room", pts: p }]);
        setPoly([]);
        setTool("select");
    };
    const upd = (id, patch) => setObjs(os => os.map(o => (o.id === id ? { ...o, ...patch } : o)));

    useEffect(() => {
        const kd = e => {
            if (/INPUT|TEXTAREA/.test(e.target.tagName)) return;
            const s = S.current,
                k = e.key;
            if (k === " ") {
                space.current = true;
                e.preventDefault();
                return;
            }
            if (k === "Escape") {
                pick("select");
                return;
            }
            if (k === "Enter") {
                closePoly();
                return;
            }
            if ((k === "Delete" || k === "Backspace") && s.sel) {
                setObjs(os => os.filter(o => o.id !== s.sel));
                setSel(null);
                return;
            }
            const l = k.toLowerCase();
            if (l === "q" && s.sel) {
                setObjs(os =>
                    os.map(o =>
                        o.id === s.sel && o.t !== "room"
                            ? { ...o, a: (o.a + (e.shiftKey ? -15 : 15) + 360) % 360 }
                            : o,
                    ),
                );
                return;
            }
            const t = TOOLS.find(x => x[1].toLowerCase() === l);
            if (t && !e.ctrlKey && !e.metaKey) pick(t[0]);
        };
        const ku = e => {
            if (e.key === " ") space.current = false;
        };
        window.addEventListener("keydown", kd);
        window.addEventListener("keyup", ku);
        return () => {
            window.removeEventListener("keydown", kd);
            window.removeEventListener("keyup", ku);
        };
    }, []);

    const toW = e => {
        const r = svg.current.getBoundingClientRect();
        return [(e.clientX - r.left - v.tx) / v.k, (e.clientY - r.top - v.ty) / v.k];
    };
    const cap = e => svg.current.setPointerCapture(e.pointerId);

    const down = e => {
        if (e.button === 2) return;
        const p = toW(e),
            sp = [snap(p[0]), snap(p[1])];
        if (e.button === 1 || tool === "pan" || space.current) {
            drag.current = { m: "pan", sx: e.clientX, sy: e.clientY, tx: v.tx, ty: v.ty };
            cap(e);
            return;
        }
        if (tool === "select") {
            const el = e.target.closest("[data-id]"),
                id = el && el.dataset.id;
            if (id) {
                setSel(id);
                const o = objs.find(o => o.id === id);
                if (o && o.t !== "room") {
                    drag.current = { m: "move", id, dx: o.x - p[0], dy: o.y - p[1] };
                    cap(e);
                }
            } else setSel(null);
            return;
        }
        if (tool === "wall") {
            if (poly.length > 2 && Math.hypot(sp[0] - poly[0][0], sp[1] - poly[0][1]) < 0.01) closePoly();
            else setPoly([...poly, sp]);
            return;
        }
        if (tool === "entry") {
            const id = nid();
            setObjs(os => [...os, { id, t: "entry", name: "Вхід", x: sp[0], y: sp[1], w: 1, h: 1, a: 0 }]);
            setSel(id);
            return;
        }
        setDraft({ t: tool, x0: sp[0], y0: sp[1], x1: sp[0], y1: sp[1] });
        cap(e);
    };

    const move = e => {
        const p = toW(e),
            sp = [snap(p[0]), snap(p[1])];
        setCur(sp);
        const d = drag.current;
        if (d && d.m === "pan")
            setV(o => ({ ...o, tx: d.tx + e.clientX - d.sx, ty: d.ty + e.clientY - d.sy }));
        else if (d && d.m === "move") upd(d.id, { x: snap(p[0] + d.dx), y: snap(p[1] + d.dy) });
        else if (draft) setDraft({ ...draft, x1: sp[0], y1: sp[1] });
    };

    const up = () => {
        drag.current = null;
        if (draft) {
            let w = Math.abs(draft.x1 - draft.x0),
                h = Math.abs(draft.y1 - draft.y0);
            const P = PRESETS[preset],
                click = draft.t === "rack" && (w < 0.5 || h < 0.5);
            if (click) {
                w = P.w;
                h = P.h;
            }
            if (w >= 0.5 && h >= 0.5) {
                const id = nid(),
                    n = objs.filter(o => o.t === draft.t).length + 1;
                const base = {
                    id,
                    t: draft.t,
                    x: click ? draft.x0 : (draft.x0 + draft.x1) / 2,
                    y: click ? draft.y0 : (draft.y0 + draft.y1) / 2,
                    w,
                    h,
                    a: 0,
                };
                const extra = {
                    rack: { name: "R-" + n, shelves: P.s },
                    obst: { name: "Колона" },
                    zin: { name: "Зона приймання", cap: 0 },
                    zout: { name: "Зона відвантаження", cap: 0 },
                }[draft.t];
                setObjs(os => [...os, { ...base, ...extra }]);
                setSel(id);
            }
            setDraft(null);
        }
    };

    const bad = useMemo(() => {
        const s = new Set(),
            room = objs.find(o => o.t === "room"),
            rk = objs.filter(o => o.t === "rack"),
            bl = objs.filter(o => o.t === "obst");
        rk.forEach(r => {
            const C = corners(r);
            if (room && !C.every(p => inPoly(p, room.pts))) s.add(r.id);
            [...rk, ...bl].forEach(o => {
                if (o.id !== r.id && hit(C, corners(o))) {
                    s.add(r.id);
                    s.add(o.id);
                }
            });
        });
        return s;
    }, [objs]);

    const flash = t => {
        setMsg(t);
        setTimeout(() => setMsg(""), 4000);
    };
    const save = async () => {
        const by = t => objs.filter(o => o.t === t),
            rc = o => ({
                id: o.id,
                name: o.name,
                coord_x: o.x,
                coord_y: o.y,
                width: o.h,
                length: o.w,
                angle: o.a,
            }),
            rm = objs.find(o => o.t === "room");
        const data = {
            format: "prostock-warehouse-map",
            version: 1,
            unit: "m",
            savedAt: new Date().toISOString(),
            room: rm ? { polygon: rm.pts, area_m2: +area(rm.pts).toFixed(2) } : null,
            racks: by("rack").map(o => ({
                ...rc(o),
                rack_code: o.name,
                shelves_count: o.shelves,
                has_conflict: bad.has(o.id),
            })),
            obstacles: by("obst").map(rc),
            zones: [...by("zin"), ...by("zout")].map(o => ({
                ...rc(o),
                zone_type: o.t === "zin" ? "Inbound_Dock" : "Outbound_Dock",
                max_capacity_m3: o.cap || 0,
            })),
            entries: by("entry").map(o => ({ id: o.id, name: o.name, coord_x: o.x, coord_y: o.y })),
        };
        try {
            const d = window.claude && (await window.claude.use("downloads"));
            if (!d) {
                flash("Збереження недоступне у цьому вікні");
                return;
            }
            await d.save({ filename: "warehouse-map.json", data: JSON.stringify(data, null, 2) });
            flash("Збережено");
        } catch (e) {
            if (!e || e.code !== "declined") flash("Не вдалося зберегти");
        }
    };
    const { k, tx, ty } = v,
        room = objs.find(o => o.t === "room"),
        so = objs.find(o => o.id === sel);
    const sw = n => n / k;
    const rectG = o => {
        const isBad = bad.has(o.id),
            on = sel === o.id,
            fs = 12 / k;
        let body,
            label = o.name,
            lc = "var(--ink)";
        if (o.t === "rack") {
            label = o.name + " · " + (o.shelves || 1) + " пол.";
            body = html`<rect
                    x=${-o.w / 2}
                    y=${-o.h / 2}
                    width=${o.w}
                    height=${o.h}
                    fill=${isBad ? "var(--bad)" : "var(--pri)"}
                    fillOpacity=".9"
                />
                ${Array.from(
                    { length: Math.max(0, (o.shelves || 1) - 1) },
                    (_, i) =>
                        html`<line
                            key=${i}
                            x1=${-o.w / 2 + ((i + 1) * o.w) / o.shelves}
                            x2=${-o.w / 2 + ((i + 1) * o.w) / o.shelves}
                            y1=${-o.h / 2}
                            y2=${o.h / 2}
                            stroke="#fff"
                            strokeOpacity=".5"
                            strokeWidth=${sw(1)}
                        />`,
                )}
                ${(o.w / (o.shelves || 1)) * k >= 18 &&
                Array.from(
                    { length: o.shelves || 1 },
                    (_, i) =>
                        html`<text
                            key=${"n" + i}
                            x=${-o.w / 2 + ((i + 0.5) * o.w) / (o.shelves || 1)}
                            y="0"
                            fontSize=${11 / k}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill="#fff"
                            pointerEvents="none"
                            >${i + 1}</text
                        >`,
                )}`;
        } else if (o.t === "obst")
            body = html`<rect
                x=${-o.w / 2}
                y=${-o.h / 2}
                width=${o.w}
                height=${o.h}
                fill=${isBad ? "var(--bad)" : "url(#hatch)"}
                fillOpacity=${isBad ? 0.6 : 1}
                stroke=${isBad ? "var(--bad)" : "var(--ink)"}
                strokeWidth=${sw(1.5)}
            />`;
        else if (o.t === "entry")
            return html`<g
                key=${o.id}
                data-id=${o.id}
                transform=${`translate(${o.x} ${o.y}) rotate(${o.a})`}
            >
                <circle r=".7" fill="var(--ok)" stroke="var(--okd)" strokeWidth=${sw(2)} /><path
                    d="M-.35 0H.35M.05 -.3L.4 0L.05 .3"
                    fill="none"
                    stroke="#2B2D42"
                    strokeWidth=${sw(2)}
                />
                ${on &&
                html`<circle
                    r=".95"
                    fill="none"
                    stroke="var(--acc)"
                    strokeWidth=${sw(2)}
                    strokeDasharray=${`${sw(5)} ${sw(3)}`}
                />`}
                <text y="1.5" fontSize=${fs} textAnchor="middle" fill="var(--ink)" pointerEvents="none"
                    >${o.name}</text
                ></g
            >`;
        else {
            const c = o.t === "zin" ? "var(--acc)" : "var(--okd)";
            body = html`<rect
                x=${-o.w / 2}
                y=${-o.h / 2}
                width=${o.w}
                height=${o.h}
                fill=${c}
                fillOpacity=".2"
                stroke=${c}
                strokeWidth=${sw(2)}
                strokeDasharray=${`${sw(7)} ${sw(4)}`}
            />`;
        }
        return html`<g key=${o.id}
            ><g data-id=${o.id} transform=${`translate(${o.x} ${o.y}) rotate(${o.a})`}
                >${body}
                ${on &&
                html`<rect
                    x=${-o.w / 2 - 0.1}
                    y=${-o.h / 2 - 0.1}
                    width=${o.w + 0.2}
                    height=${o.h + 0.2}
                    fill="none"
                    stroke="var(--acc)"
                    strokeWidth=${sw(2.5)}
                    strokeDasharray=${`${sw(6)} ${sw(3)}`}
                />`}</g
            >
            <text
                x=${o.t === "rack" ? o.x + Math.sin((o.a * Math.PI) / 180) * (o.h / 2 + fs) : o.x}
                y=${o.t === "rack" ? o.y - Math.cos((o.a * Math.PI) / 180) * (o.h / 2 + fs) : o.y}
                fontSize=${fs}
                textAnchor="middle"
                dominantBaseline="central"
                fill=${lc}
                pointerEvents="none"
                >${label}</text
            ></g
        >`;
    };

    const dw = draft ? Math.abs(draft.x1 - draft.x0) : 0,
        dh = draft ? Math.abs(draft.y1 - draft.y0) : 0;
    const F = (label, val, on, p) =>
        html`<label className="f"
            ><span>${label}</span
            ><input
                type=${p ? "number" : "text"}
                step=${p && p.step}
                min=${p && p.min}
                value=${val}
                onChange=${e => {
                    if (!p) return on(e.target.value);
                    const n = parseFloat(e.target.value);
                    if (!isNaN(n)) on(n);
                }}
        /></label>`;
    const cursor = tool === "pan" ? "grab" : tool === "select" ? "default" : "crosshair";

    return html`<div className="app">
        <div className="top">
            <b>ProStock</b><span>Конструктор складу · 2D-мапа</span
            ><button className="sv" onClick=${save}>Зберегти JSON</button>
        </div>
        <div className="main">
            <div className="tools">
                ${TOOLS.map(
                    ([id, key, name, ic]) =>
                        html`<button
                            key=${id}
                            className=${"tb" + (tool === id ? " on" : "")}
                            title=${name + " (" + key + ")"}
                            onClick=${() => pick(id)}
                        >
                            <i>${ic}</i><small>${name}</small>
                        </button>`,
                )}
            </div>
            <div className="cv" ref=${wrap}>
                <svg
                    ref=${svg}
                    style=${{ cursor }}
                    onPointerDown=${down}
                    onPointerMove=${move}
                    onPointerUp=${up}
                    onContextMenu=${e => e.preventDefault()}
                >
                    <defs>
                        <pattern id="g1" width="1" height="1" patternUnits="userSpaceOnUse">
                            <path d="M1 0H0V1" fill="none" stroke="var(--gm)" strokeWidth=${sw(1)} />
                        </pattern>
                        <pattern id="g5" width="5" height="5" patternUnits="userSpaceOnUse">
                            <path d="M5 0H0V5" fill="none" stroke="var(--gM)" strokeWidth=${sw(1)} />
                        </pattern>
                        <pattern
                            id="hatch"
                            width=".4"
                            height=".4"
                            patternUnits="userSpaceOnUse"
                            patternTransform="rotate(45)"
                        >
                            <line x1="0" y1="0" x2="0" y2=".4" stroke="var(--ink)" strokeWidth=".1" />
                        </pattern>
                    </defs>
                    <g transform=${`translate(${tx} ${ty}) scale(${k})`}>
                        ${k >= 10 &&
                        html`<rect
                            x=${-tx / k}
                            y=${-ty / k}
                            width=${sz.w / k}
                            height=${sz.h / k}
                            fill="url(#g1)"
                            pointerEvents="none"
                        />`}
                        <rect
                            x=${-tx / k}
                            y=${-ty / k}
                            width=${sz.w / k}
                            height=${sz.h / k}
                            fill="url(#g5)"
                            pointerEvents="none"
                        />
                        <path
                            d=${`M${-tx / k} 0H${(sz.w - tx) / k}M0 ${-ty / k}V${(sz.h - ty) / k}`}
                            stroke="var(--acc)"
                            strokeOpacity=".7"
                            strokeWidth=${sw(1.5)}
                            pointerEvents="none"
                        />
                        ${room &&
                        html`<polygon
                            data-id=${room.id}
                            points=${room.pts.map(p => p.join(",")).join(" ")}
                            fill="var(--room)"
                            stroke=${sel === room.id ? "var(--acc)" : "var(--pri)"}
                            strokeWidth=".35"
                            strokeLinejoin="miter"
                        />`}
                        ${room &&
                        html`<polygon
                            points=${room.pts.map(p => p.join(",")).join(" ")}
                            fill="url(#g1)"
                            pointerEvents="none"
                        />`}
                        ${objs.filter(o => o.t !== "room" && o.t !== "entry").map(rectG)}
                        ${objs.filter(o => o.t === "entry").map(rectG)}
                        ${poly.length > 0 &&
                        html`<g pointerEvents="none"
                            ><polyline
                                points=${[...poly, cur].map(p => p.join(",")).join(" ")}
                                fill="none"
                                stroke="var(--acc)"
                                strokeWidth=${sw(2.5)}
                            />
                            ${poly.map(
                                (p, i) =>
                                    html`<circle
                                        key=${i}
                                        cx=${p[0]}
                                        cy=${p[1]}
                                        r=${sw(i === 0 ? 7 : 4)}
                                        fill=${i === 0 ? "var(--ok)" : "var(--acc)"}
                                    />`,
                            )}
                            <text x=${cur[0] + 0.4} y=${cur[1] - 0.4} fontSize=${12 / k} fill="var(--ink)"
                                >${Math.hypot(
                                    cur[0] - poly[poly.length - 1][0],
                                    cur[1] - poly[poly.length - 1][1],
                                ).toFixed(1)}
                                м</text
                            ></g
                        >`}
                        ${draft &&
                        html`<g pointerEvents="none"
                            ><rect
                                x=${Math.min(draft.x0, draft.x1)}
                                y=${Math.min(draft.y0, draft.y1)}
                                width=${dw}
                                height=${dh}
                                fill="var(--acc)"
                                fillOpacity=".25"
                                stroke="var(--acc)"
                                strokeWidth=${sw(2)}
                            />
                            <text
                                x=${Math.max(draft.x0, draft.x1) + 0.3}
                                y=${Math.min(draft.y0, draft.y1) - 0.3}
                                fontSize=${12 / k}
                                fill="var(--ink)"
                                >${dw.toFixed(1)} × ${dh.toFixed(1)} м</text
                            ></g
                        >`}
                        ${tool === "rack" &&
                        !draft &&
                        html`<rect
                            x=${cur[0] - PRESETS[preset].w / 2}
                            y=${cur[1] - PRESETS[preset].h / 2}
                            width=${PRESETS[preset].w}
                            height=${PRESETS[preset].h}
                            fill="var(--pri)"
                            fillOpacity=".22"
                            stroke="var(--pri)"
                            strokeWidth=${sw(1.5)}
                            strokeDasharray=${`${sw(5)} ${sw(3)}`}
                            pointerEvents="none"
                        />`}
                        ${tool !== "select" &&
                        tool !== "pan" &&
                        html`<path
                            d=${`M${cur[0] - 0.6} ${cur[1]}H${cur[0] + 0.6}M${cur[0]} ${cur[1] - 0.6}V${cur[1] + 0.6}`}
                            stroke="var(--ink)"
                            strokeWidth=${sw(1)}
                            pointerEvents="none"
                        />`}
                    </g>
                </svg>
                <div className="hint">${HINT[tool]}</div>
            </div>
            <div className="panel">
                ${so && so.t !== "room"
                    ? html`<h4>Властивості</h4>
                          ${F("Назва", so.name, x => upd(so.id, { name: x }))}
                          ${so.t !== "entry" &&
                          F("Ширина, м", so.w, x => upd(so.id, { w: Math.max(0.5, x) }), {
                              step: 0.5,
                              min: 0.5,
                          })}
                          ${so.t !== "entry" &&
                          F("Довжина, м", so.h, x => upd(so.id, { h: Math.max(0.5, x) }), {
                              step: 0.5,
                              min: 0.5,
                          })}
                          ${F("X, м", so.x, x => upd(so.id, { x }), { step: 0.5 })}${F(
                              "Y, м",
                              so.y,
                              x => upd(so.id, { y: x }),
                              { step: 0.5 },
                          )}
                          ${F("Кут, °", so.a, x => upd(so.id, { a: x }), { step: 15 })}
                          ${so.t === "rack" &&
                          F(
                              "Полиць",
                              so.shelves,
                              x => upd(so.id, { shelves: Math.max(1, Math.round(x)) }),
                              { step: 1, min: 1 },
                          )}
                          ${(so.t === "zin" || so.t === "zout") &&
                          F("Місткість, м³", so.cap, x => upd(so.id, { cap: Math.max(0, x) }), {
                              step: 1,
                              min: 0,
                          })}
                          ${bad.has(so.id) &&
                          html`<div className="bad" style=${{ color: "var(--bad)", marginTop: 4 }}>
                              ⚠ Колізія або вихід за межі приміщення
                          </div>`}
                          <button
                              className="btn d"
                              onClick=${() => {
                                  setObjs(os => os.filter(o => o.id !== so.id));
                                  setSel(null);
                              }}
                          >
                              Видалити
                          </button>`
                    : html`<h4>${so ? "Контур приміщення" : "Об’єкти"}</h4>
                          ${so
                              ? html`<button
                                    className="btn d"
                                    onClick=${() => {
                                        setObjs(os => os.filter(o => o.id !== so.id));
                                        setSel(null);
                                    }}
                                >
                                    Видалити контур
                                </button>`
                              : html`<div style=${{ color: "var(--mut)", marginBottom: 10 }}>
                                    Оберіть об’єкт на мапі, щоб змінити параметри.
                                </div>`}`}
                <h4 style=${{ marginTop: 18 }}>Пресети стелажів</h4>
                ${PRESETS.map(
                    (p, i) =>
                        html`<button
                            key=${i}
                            className=${"btn p" + (preset === i ? " on" : "")}
                            onClick=${() => {
                                setPreset(i);
                                if (so && so.t === "rack") upd(so.id, { w: p.w, h: p.h, shelves: p.s });
                                else pick("rack");
                            }}
                        >
                            ${p.n}<br /><small>${p.w} × ${p.h} м · ${p.s} пол.</small>
                        </button>`,
                )}
                <h4 style=${{ marginTop: 18 }}>Умовні позначення</h4>
                <div className="lg"><s style=${{ background: "var(--pri)" }} />Стелаж</div>
                <div className="lg"><s style=${{ background: "var(--bad)" }} />Колізія</div>
                <div className="lg">
                    <s style=${{ background: "var(--acc)", opacity: 0.5 }} />Зона приймання
                </div>
                <div className="lg">
                    <s style=${{ background: "var(--okd)", opacity: 0.5 }} />Зона відвантаження
                </div>
                <div className="lg">
                    <s style=${{ background: "var(--ok)", borderRadius: "50%" }} />Точка входу
                </div>
            </div>
        </div>
        <div className="st">
            <span>X: ${cur[0].toFixed(1)} м · Y: ${cur[1].toFixed(1)} м</span
            ><span>Масштаб: ${((k / 22) * 100).toFixed(0)}%</span><span>Крок: 0,5 м</span>${msg &&
            html`<span>${msg}</span>`}
            <span>Стелажів: ${objs.filter(o => o.t === "rack").length}</span>${room &&
            html`<span>Площа: ${area(room.pts).toFixed(0)} м²</span>`}
            <span className=${bad.size ? "bad" : ""}>Конфліктів: ${bad.size}</span>
        </div>
    </div>`;
}
ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);

