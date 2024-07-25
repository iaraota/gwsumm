
function adjustDate(days) {
    /**
     * Adjusts the date in the current page URL by a specified number of days.
     *
     * This function extracts a date in `YYYYMMDD` format from the current page URL,
     * adjusts this date by adding or subtracting a specified number of days,
     * and then updates the URL with the new date.
     *
     * @param {number} days - The number of days to add (or subtract if negative) from the current date.
     * @returns {string} The updated URL with the adjusted date.
     */

    var url = window.location.href;
    
    var dateStr = url.match(/\b\d{8}\b/);
    if (dateStr) {
        dateStr = dateStr[0];
    }
    
    var year = parseInt(dateStr.substring(0, 4), 10);
    // Month is zero-based, needs to subtract 1
    var month = parseInt(dateStr.substring(4, 6), 10) - 1; 
    var day = parseInt(dateStr.substring(6, 8), 10);

    var date = new Date(year, month, day);
    date.setDate(date.getDate() + days);
    
    var adjustedYear = date.getFullYear();
    // Months are zero-based, add leading zero if month/day is a single digit
    var adjustedMonth = ('0' + (date.getMonth() + 1)).slice(-2); 
    var adjustedDay = ('0' + date.getDate()).slice(-2); 
    
    var adjustedDate = adjustedYear + adjustedMonth + adjustedDay;
    
    return url.replace(dateStr, adjustedDate);
}

/**
 * Initializes Fancybox for elements with the data attribute `data-fancybox="gallery"`.
 *
 * Binds Fancybox to gallery items and customizes the toolbar with two buttons:
 * - A "previousDay" button to navigate to the previous day.
 * - A "nextDay" button to navigate to the next day.
 *
 * Clicking these buttons updates the page URL to reflect the new date.
 */
jQuery(window).on('load', function () {
    Fancybox.bind('[data-fancybox="gallery"]', {
        Toolbar: {
            items: {
                previousDay: {
                    tpl: '<button class="f-button fancybox-button--previousDay" data-fancybox-previousDay>' +
                        '<svg viewBox="0 0 40 40">' +
                        '<path d="M25 10 L15 20 L25 30" />' + // Left arrow
                        '</svg>' +
                        '</button>',
                    click: () => {
                        window.location.href = adjustDate(-1);
                    },
                },
                nextDay: {
                    tpl: '<button class="f-button fancybox-button--nextDay" data-fancybox-nextDay>' +
                        '<svg viewBox="0 0 40 40">' +
                        '<path d="M15 10 L25 20 L15 30" />' + // Right arrow
                        '</svg>' +
                        '</button>',
                    click: () => {
                        window.location.href = adjustDate(1);
                    },
                },
            },
            display: {
                middle: ["previousDay", "nextDay"],
            },
        },
    });
});