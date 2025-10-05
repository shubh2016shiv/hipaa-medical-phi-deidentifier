/**
 * Synchronized Scrolling for DEID Patients
 * 
 * This script provides synchronized scrolling between two iframes
 * for side-by-side comparison of original and de-identified text.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for iframes to load
    setTimeout(initSyncScroll, 1000);
});

function initSyncScroll() {
    // Get the iframe elements
    const leftFrame = document.getElementById('highlighted-text-frame');
    const rightFrame = document.getElementById('deidentified-text-frame');
    
    if (!leftFrame || !rightFrame) {
        console.log('Iframes not found, retrying in 1 second...');
        setTimeout(initSyncScroll, 1000);
        return;
    }
    
    console.log('Initializing synchronized scrolling...');
    
    // Variables to prevent infinite scroll loops
    let isLeftScrolling = false;
    let isRightScrolling = false;
    
    // Function to sync scroll from left to right
    function syncLeftToRight() {
        if (!isRightScrolling && leftFrame.contentWindow && rightFrame.contentWindow) {
            isLeftScrolling = true;
            
            // Calculate scroll percentage
            const leftDoc = leftFrame.contentDocument || leftFrame.contentWindow.document;
            const leftScrollHeight = leftDoc.documentElement.scrollHeight - leftDoc.documentElement.clientHeight;
            const leftScrollPercentage = leftDoc.documentElement.scrollTop / leftScrollHeight;
            
            // Apply to right frame
            const rightDoc = rightFrame.contentDocument || rightFrame.contentWindow.document;
            const rightScrollHeight = rightDoc.documentElement.scrollHeight - rightDoc.documentElement.clientHeight;
            rightDoc.documentElement.scrollTop = leftScrollPercentage * rightScrollHeight;
            
            // Reset flag after a short delay
            setTimeout(() => { isLeftScrolling = false; }, 50);
        }
    }
    
    // Function to sync scroll from right to left
    function syncRightToLeft() {
        if (!isLeftScrolling && rightFrame.contentWindow && leftFrame.contentWindow) {
            isRightScrolling = true;
            
            // Calculate scroll percentage
            const rightDoc = rightFrame.contentDocument || rightFrame.contentWindow.document;
            const rightScrollHeight = rightDoc.documentElement.scrollHeight - rightDoc.documentElement.clientHeight;
            const rightScrollPercentage = rightDoc.documentElement.scrollTop / rightScrollHeight;
            
            // Apply to left frame
            const leftDoc = leftFrame.contentDocument || leftFrame.contentWindow.document;
            const leftScrollHeight = leftDoc.documentElement.scrollHeight - leftDoc.documentElement.clientHeight;
            leftDoc.documentElement.scrollTop = rightScrollPercentage * leftScrollHeight;
            
            // Reset flag after a short delay
            setTimeout(() => { isRightScrolling = false; }, 50);
        }
    }
    
    // Try to access iframe content and set up event listeners
    try {
        // Access left iframe
        leftFrame.onload = function() {
            try {
                const leftDoc = leftFrame.contentDocument || leftFrame.contentWindow.document;
                leftDoc.addEventListener('scroll', syncLeftToRight);
                console.log('Left iframe scroll listener added');
            } catch (e) {
                console.error('Error setting up left iframe scroll listener:', e);
            }
        };
        
        // Access right iframe
        rightFrame.onload = function() {
            try {
                const rightDoc = rightFrame.contentDocument || rightFrame.contentWindow.document;
                rightDoc.addEventListener('scroll', syncRightToLeft);
                console.log('Right iframe scroll listener added');
            } catch (e) {
                console.error('Error setting up right iframe scroll listener:', e);
            }
        };
        
        // If iframes are already loaded, add listeners now
        if (leftFrame.contentDocument || leftFrame.contentWindow) {
            const leftDoc = leftFrame.contentDocument || leftFrame.contentWindow.document;
            leftDoc.addEventListener('scroll', syncLeftToRight);
            console.log('Left iframe scroll listener added (already loaded)');
        }
        
        if (rightFrame.contentDocument || rightFrame.contentWindow) {
            const rightDoc = rightFrame.contentDocument || rightFrame.contentWindow.document;
            rightDoc.addEventListener('scroll', syncRightToLeft);
            console.log('Right iframe scroll listener added (already loaded)');
        }
        
        console.log('Synchronized scrolling initialized successfully');
    } catch (e) {
        console.error('Error initializing synchronized scrolling:', e);
    }
}


