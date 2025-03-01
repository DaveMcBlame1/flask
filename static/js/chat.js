document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const chatbox = document.getElementById('chatbox');
    const messageInput = document.getElementById('message');
    const sendButton = document.getElementById('send');
    const loadMoreButton = document.getElementById('load-more');
    const userList = document.querySelector('.user-list .users'); // Corrected selector
    const typingIndicator = document.getElementById('typing-indicator');
    let offset = 50;  // Initial offset for loading more messages
    let typing = false;
    let timeout;
    let typingUsers = new Set();
    let typingAnimationInterval;

    function scrollToBottom() {
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    // Scroll to the bottom when the page loads
    window.onload = function() {
        scrollToBottom();
        const savedTheme = localStorage.getItem('selectedTheme');
        if (savedTheme) {
            setTheme(savedTheme);
        } else {
            setTheme('default'); // Default theme
        }
    };

    // Handle the custom event for forced disconnection
    socket.on('force_disconnect', (data) => {
        alert(data.message);
        // Optionally, you can redirect the user to the login page or another page
        window.location.href = '/login';
    });

    socket.on('message', function(data) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');

        const profilePicture = document.createElement('img');
        profilePicture.classList.add('pfp');
        profilePicture.src = data.profile_picture_url;
        profilePicture.alt = 'Profile Picture';

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');

        const messageHeader = document.createElement('div');
        messageHeader.classList.add('message-header');

        const username = document.createElement('span');
        username.classList.add('username');
        username.textContent = `${data.username}:`;

        const messageId = document.createElement('span');
        messageId.classList.add('message-id');
        messageId.dataset.id = data.message_id;
        messageId.textContent = data.message_id;

        const messageBody = document.createElement('div');
        messageBody.classList.add('message-body');
        messageBody.textContent = data.message;

        messageHeader.appendChild(username);
        messageHeader.appendChild(messageId);
        messageContent.appendChild(messageHeader);
        messageContent.appendChild(messageBody);
        messageElement.appendChild(profilePicture);
        messageElement.appendChild(messageContent);
        chatbox.appendChild(messageElement);
        scrollToBottom(); // Scroll to the bottom when a new message is received

        // If the message is a system message, remove it after 5 seconds
        if (data.system) {
            setTimeout(() => {
                chatbox.removeChild(messageElement);
            }, 5000);
        }
    });

    socket.on('message_deleted', function(data) {
        console.log('Deleting message with ID:', data.message_id); // Debugging
        const messageElement = document.querySelector(`.message-id[data-id="${data.message_id}"]`);
        if (messageElement) {
            const parentElement = messageElement.closest('.message');
            if (parentElement) {
                parentElement.remove();
            } else {
                console.error('Parent element not found for message ID:', data.message_id);
            }
        } else {
            console.error('Message element not found for message ID:', data.message_id);
        }
    });

    socket.on('update_user_list', function(users) {
        userList.innerHTML = '';  // Clear the current list
        users.forEach(function(user) {
            const userElement = document.createElement('p');
            userElement.classList.add('viewer');
            userElement.textContent = user;
            userList.appendChild(userElement);
        });
    });

    socket.on('user_typing', function(data) {
        typingUsers.add(data.username);
        updateTypingIndicator();
    });

    socket.on('user_stopped_typing', function(data) {
        typingUsers.delete(data.username);
        updateTypingIndicator();
    });

    function startTypingAnimation() {
        let dots = 0;
        typingAnimationInterval = setInterval(() => {
            dots = (dots + 1) % 4;
            const dotString = '.'.repeat(dots);
            typingIndicator.textContent = `${Array.from(typingUsers).join(', ')} ${typingUsers.size > 1 ? 'are' : 'is'} typing${dotString}`;
        }, 175);
    }

    function stopTypingAnimation() {
        clearInterval(typingAnimationInterval);
        typingIndicator.textContent = '';
    }

    function updateTypingIndicator() {
        if (typingUsers.size > 0) {
            startTypingAnimation();
        } else {
            stopTypingAnimation();
        }
    }

    messageInput.addEventListener('input', function() {
        if (!typing) {
            typing = true;
            socket.emit('typing');
            timeout = setTimeout(stopTyping, 1000); // Stop typing after 1 second of inactivity
        } else {
            clearTimeout(timeout);
            timeout = setTimeout(stopTyping, 1000);
        }
    });

    function stopTyping() {
        typing = false;
        socket.emit('stop_typing');
    }

    sendButton.addEventListener('click', function() {
        const message = messageInput.value;
        const trimmedMessage = message.trim();
        if (trimmedMessage === '') {
            return;  // Do not send the message if it is empty or just whitespace
        }
        if (message) {
            if (message.startsWith('/delete ')) {
                // Check for user permissions
                if (!AUTHORIZED_USERS.includes(username)) {
                    alert('You do not have permission to delete messages');
                    return;
                }

                const messageId = message.split(' ')[1];
                const messageElement = document.querySelector(`.message-id[data-id="${messageId}"]`);
                if (messageElement) {
                    const parentElement = messageElement.closest('.message');
                    if (parentElement) {
                        parentElement.remove();
                        socket.emit('delete_message', { message_id: messageId });
                    } else {
                        console.error('Parent element not found for message ID:', messageId);
                    }
                } else {
                    console.error('Message element not found for message ID:', messageId);
                }
            } else {
                socket.emit('message', { message: message });
            }
            messageInput.value = '';
            scrollToBottom(); // Scroll to the bottom after sending a message
            stopTyping(); // Stop typing when the message is sent
        }
    });

    messageInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendButton.click();
        }
    });

    loadMoreButton.addEventListener('click', function() {
        fetch(`/more_messages/${offset}`)
            .then(response => response.json())
            .then(data => {
                // Reverse the order of the messages to display the oldest first
                data.reverse().forEach(msg => {
                    const messageElement = document.createElement('div');
                    messageElement.classList.add('message');
                    messageElement.innerHTML = `
                            <img class="pfp" src="${msg.profile_picture_url}" alt="Profile Picture">
                            <div class="message-content">
                                <div class="message-header">
                                    <span class="username">${msg.username}:</span>
                                    <span class="message-id" data-id="${msg.id}">${msg.id}</span>
                                </div>
                                <div class="message-body">
                                    ${msg.message}
                                </div>
                            </div>
                        </div>
                    `;
                    chatbox.insertBefore(messageElement, chatbox.firstChild);
                });
                offset += 25;  // Increase the offset for the next set of messages
            })
            .catch(error => console.error('Error loading more messages:', error));
    });

    // Function to set the theme
    function setTheme(themeName) {
        const themeLink = document.getElementById('theme-link');
        if (themeLink) {
            themeLink.href = `/static/themes/${themeName}.css`;
        }
    }
});