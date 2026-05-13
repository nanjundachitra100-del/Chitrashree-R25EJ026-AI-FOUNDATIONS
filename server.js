const express = require('express');
const cors = require('cors');
const axios = require('axios');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.static(path.join(__dirname)));

app.get(['/', '/index.html'], (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

const PORT = 3000;
const WIKI_API_URL = 'https://en.wikipedia.org/w/api.php';
const WIKI_HEADERS = {
    'User-Agent': 'TouristGuidePracticeApp/1.0 (https://example.com)'
};

function formatPage(page) {
    return {
        id: page.pageid.toString(),
        name: page.title,
        img: page.thumbnail?.source || 'https://via.placeholder.com/500x300?text=No+Image',
        shortDesc: page.extract || 'No description available.',
        fullDesc: page.extract || 'No details available.',
        timings: 'Timing information not available',
        rating: 'N/A',
        phone: 'Not available',
        website: page.fullurl || 'Not available'
    };
}

async function searchWikipediaPlaces(city) {
    const response = await axios.get(WIKI_API_URL, {
        headers: WIKI_HEADERS,
        params: {
            action: 'query',
            format: 'json',
            origin: '*',
            generator: 'search',
            gsrlimit: 10,
            gsrsearch: `tourist attractions in ${city}`,
            prop: 'pageimages|extracts|info',
            exintro: true,
            explaintext: true,
            pilimit: 'max',
            pithumbsize: 500,
            inprop: 'url'
        }
    });

    const pages = response.data.query?.pages || {};
    return Object.values(pages)
        .sort((a, b) => (a.index || 0) - (b.index || 0))
        .map(formatPage);
}

async function getWikipediaPlaceDetails(pageId) {
    const response = await axios.get(WIKI_API_URL, {
        headers: WIKI_HEADERS,
        params: {
            action: 'query',
            format: 'json',
            origin: '*',
            pageids: pageId,
            prop: 'pageimages|extracts|info',
            exintro: true,
            explaintext: true,
            pithumbsize: 800,
            inprop: 'url'
        }
    });

    const pages = response.data.query?.pages || {};
    const page = pages[pageId] || Object.values(pages)[0];
    return page ? formatPage(page) : null;
}

/* SEARCH PLACES */
app.get('/api/places', async (req, res) => {
    const city = req.query.city?.trim();

    if (!city) {
        return res.status(400).json({ message: 'Enter a city' });
    }

    try {
        const places = await searchWikipediaPlaces(city);
        res.json(places);
    } catch (error) {
        console.error('Search Error:', error.response?.data || error.message);
        res.status(500).json({ message: 'Wikipedia fetch failed' });
    }
});

/* DETAILS */
app.get('/api/place/:id', async (req, res) => {
    const id = req.params.id;

    try {
        const place = await getWikipediaPlaceDetails(id);

        if (!place) {
            return res.status(404).json({ message: 'Place not found' });
        }

        res.json(place);
    } catch (error) {
        console.error('Details Error:', error.response?.data || error.message);
        res.status(500).json({ message: 'Wikipedia details failed' });
    }
});

app.listen(PORT, () => {
    console.log(`Server running at http://127.0.0.1:${PORT}`);
});