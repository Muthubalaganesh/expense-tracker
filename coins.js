document.addEventListener('DOMContentLoaded', function() {
    fetch('/coin-data')  // Fetching coin data from the server
        .then(response => response.json()) // Parsing the JSON response
        .then(coins => {
            const container = document.querySelector('.coin-background'); // Selecting the container
            coins.forEach(coin => {
                const element = document.createElement('div'); // Creating a coin element
                element.className = 'coin';
                element.style.cssText = `
                    width: ${coin.size}px;
                    height: ${coin.size}px;
                    left: ${coin.left}%;
                    animation-duration: ${coin.duration}s;
                    animation-delay: ${coin.delay}s;
                `;
                container.appendChild(element); // Adding the coin to the container
            });
        });
});
