const snap = v => Math.round(v * 2) / 2;
let _n = 100;
const nid = () => "o" + _n++;

// геометрія: SAT для повернутих прямокутників, точка в полігоні
const corners = o => {
    const r = (o.a * Math.PI) / 180,
        c = Math.cos(r),
        s = Math.sin(r);
    return [
        [-1, -1],
        [1, -1],
        [1, 1],
        [-1, 1],
    ].map(([i, j]) => {
        const x = (i * o.w) / 2,
            y = (j * o.h) / 2;
        return [o.x + x * c - y * s, o.y + x * s + y * c];
    });
};
const axes = p =>
    p.map((a, i) => {
        const b = p[(i + 1) % p.length];
        return [-(b[1] - a[1]), b[0] - a[0]];
    });
const proj = (p, ax) => {
    let mn = 1e9,
        mx = -1e9;
    p.forEach(q => {
        const d = q[0] * ax[0] + q[1] * ax[1];
        mn = Math.min(mn, d);
        mx = Math.max(mx, d);
    });
    return [mn, mx];
};
const hit = (A, B) =>
    [...axes(A), ...axes(B)].every(ax => {
        const a = proj(A, ax),
            b = proj(B, ax);
        return a[1] > b[0] + 1e-6 && b[1] > a[0] + 1e-6;
    });
const inPoly = (pt, poly) => {
    let c = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [a, b] = poly[i],
            [d, e] = poly[j];
        if (b > pt[1] !== e > pt[1] && pt[0] < ((d - a) * (pt[1] - b)) / (e - b) + a) c = !c;
    }
    return c;
};
const area = p =>
    Math.abs(
        p.reduce((s, a, i) => {
            const b = p[(i + 1) % p.length];
            return s + a[0] * b[1] - b[0] * a[1];
        }, 0),
    ) / 2;


