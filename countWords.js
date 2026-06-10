const fs = require("fs");
const path = require("path");

const dirPath = process.argv[2];
const words = process.argv.slice(3);

if (!dirPath || words.length === 0) {
    console.error("Usage: node countWords.js <directory> <word1> <word2> ...");
    process.exit(1);
}

// Escape regex characters
const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Precompile regexes
const wordRegexes = words.reduce((acc, word) => {
    acc[word] = new RegExp(`\\b${escapeRegex(word)}\\b`, "gi");
    return acc;
}, {});

const totals = Object.fromEntries(words.map(w => [w, 0]));

function processFile(filePath) {
    const text = fs.readFileSync(filePath, "utf8");

    const counts = [];
    for (const word of words) {
        const matches = text.match(wordRegexes[word]);
        const count = matches ? matches.length : 0;
        totals[word] += count;
        counts.push(count);
    }
    if (counts.length > 0 && (counts[0] != counts[1])) {
        console.log(`\nFile: ${filePath}`);
        console.log('diff', counts[0] - counts[1]);
    }
}

function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            walk(fullPath);
        } else if (entry.isFile()) {
            processFile(fullPath);
        }
    }
}

walk(path.resolve(dirPath));

console.log("\n=== TOTALS ===");
for (const word of words) {
    console.log(`${word}: ${totals[word]}`);
}
console.log('diff', totals['GLOBAL_ASM'] - totals['NON_MATCHING']);