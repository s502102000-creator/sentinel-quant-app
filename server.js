const express = require('express');
const cors = require('cors');
const path = require('path');
const indicatorsFunc = require('./netlify/functions/indicators');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.static(path.join(__dirname)));

app.get('/api/indicators', async (req, res) => {
    const result = await indicatorsFunc.handler({}, {});
    res.status(result.statusCode).set(result.headers).send(result.body);
});

app.get('/.netlify/functions/indicators', async (req, res) => {
    const result = await indicatorsFunc.handler({}, {});
    res.status(result.statusCode).set(result.headers).send(result.body);
});

app.listen(PORT, () => {
    console.log(`Sentinel Quant Backend running on http://localhost:${PORT}`);
});
