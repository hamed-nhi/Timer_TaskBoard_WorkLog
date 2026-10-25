const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const filename = path.resolve(__dirname, "../../src/lib/format.ts");
const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(compiled, filename);
const f = loaded.exports;

for (const [value, expected] of [["930", "09:30"], ["۰۹۳۰", "09:30"], ["٢٣٥٩", "23:59"], ["9", "09:00"]]) {
  test("clock parsing: " + value, () => assert.deepEqual(f.parseTimeText(value), { state: "ok", value: expected }));
}
for (const value of ["2460", "2360", "99999"]) {
  test("invalid clock: " + value, () => assert.equal(f.parseTimeText(value).state, "bad"));
}
test("Persian/Arabic digits normalize both ways", () => {
  assert.equal(f.fa("0123 ٤٥٦"), "۰۱۲۳ ۴۵۶");
  assert.equal(f.latin("۰۱۲۳ ٤٥٦"), "0123 456");
});
test("midnight time span", () => assert.equal(f.spanMinutes("23:59", "00:00"), 1));
test("rounded duration never displays sixty remainder minutes", () => assert.equal(f.fmtDuration(119.6), "۲ ساعت ۰ دقیقه"));
test("zero minutes remain visible", () => assert.equal(f.fmtHM(0), "۰:۰۰"));
test("unknown tag and no tag have stable colors", () => {
  assert.equal(f.tagColor(null, []), f.NO_TAG_COLOR);
  assert.equal(f.tagColor(7, [7, 3]), f.tagColor(7, [3, 7]));
});
