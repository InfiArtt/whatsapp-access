// WhatsApp Access add-on
// Copyright (C) 2026 InfiArtt
// This file is covered by the GNU General Public License.
//
// Installed into the WhatsApp Web page by the add-on through the browser's remote debugging.
// It reads chats and messages from WhatsApp Web's own modules and sends what the user writes or records.
// Everything WhatsApp-specific lives here, so a WhatsApp update usually needs changes in this file only.
// It never sends anything on its own: every send is a call the user started in the add-on.
(() => {
	"use strict";
	const VERSION = 1;
	const EVENT_BINDING = "__waAccessEvent";
	// The add-on installs this once per connection or page load. A copy from an earlier connection is replaced.
	const old = window.__waAccess;
	if (old && old.unhook) {
		old.unhook();
	}

	const req = (name) => window.require(name);
	const collections = () => req("WAWebCollections");

	function emit(event) {
		const binding = window[EVENT_BINDING];
		if (typeof binding === "function") {
			try {
				binding(JSON.stringify(event));
			} catch (e) {
				// The add-on is gone; nothing to tell.
			}
		}
	}

	function ready() {
		try {
			return typeof window.require === "function" && collections().Chat.getModelsArray().length > 0;
		} catch (e) {
			return false;
		}
	}

	// Logging in --------------------------------------------------------------------------------------

	// Where WhatsApp Web is: still loading, waiting to be linked to a phone, or linked with chats loaded.
	function authState() {
		let socket = "LOADING";
		try {
			socket = req("WAWebSocketModel").Socket.state || "LOADING";
		} catch (e) {
			// Not loaded yet.
		}
		const linked = socket !== "LOADING" && !String(socket).startsWith("UN") && socket !== "PAIRING";
		return { socket: String(socket), needsLink: String(socket).startsWith("UNPAIRED"), ready: linked && ready() };
	}

	// Asks WhatsApp for the 8-character code to type on the phone, instead of scanning the QR code.
	// The phone shows a notification asking for it.
	async function requestLinkCode(phone) {
		const digits = String(phone || "").replace(/[^0-9]/g, "");
		if (digits.length < 6) {
			throw new Error("badNumber");
		}
		const linking = req("WAWebAltDeviceLinkingApi");
		linking.setPairingType("ALT_DEVICE_LINKING");
		await linking.initializeAltDeviceLinking();
		return String(await linking.startAltLinkingFlow(digits, true));
	}

	// Unlinks this browser from the phone's linked devices, as "Log out" in WhatsApp Web does.
	async function logout() {
		await req("WAWebSocketModel").Socket.logout();
		return true;
	}

	// Chats ----------------------------------------------------------------------------------------------

	function isListedChat(chat) {
		const server = chat.id && chat.id.server;
		return server !== "broadcast" && server !== "newsletter";
	}

	// Newer WhatsApp versions have no isGroup on chats; group ids end in @g.us.
	function isGroupChat(chat) {
		return !!(chat.isGroup || (chat.id && chat.id.server === "g.us"));
	}

	function chatTitle(chat) {
		return chat.formattedTitle || chat.name || (chat.contact && chat.contact.formattedName) || chat.id.user || "";
	}

	// Sending to "status@broadcast" posts the user's own status; that chat is not in the chat list.
	function chatOrStatus(chatId) {
		return chatId === "status@broadcast" ? req("WAWebStatusJidUtils").getStatusChat() : getChat(chatId);
	}

	// Channels are not in Chat but in their own collection; they open, read and react like chats.
	function getChat(chatId) {
		const C = collections();
		const chat = C.Chat.get(chatId) || (C.WAWebNewsletterCollection && C.WAWebNewsletterCollection.get(chatId));
		if (!chat) {
			throw new Error("chatNotFound");
		}
		return chat;
	}

	// Newer WhatsApp versions no longer fill in _serialized for message ids; toString() gives the same text.
	function msgId(m) {
		return m.id._serialized || m.id.toString();
	}

	function getMsg(messageId) {
		const C = collections();
		let m = C.Msg.get(messageId);
		if (!m && C.Status) {
			for (const status of C.Status.getModelsArray()) {
				const found = status.msgs && status.msgs.get(messageId);
				if (found) {
					m = found;
					break;
				}
			}
		}
		if (!m) {
			throw new Error("messageNotFound");
		}
		return m;
	}

	// The name the user saved for a contact, else the name the person gave themselves in WhatsApp.
	function personName(contact) {
		if (!contact) {
			return null;
		}
		const name = contact.formattedName || contact.name || contact.pushname || contact.verifiedName || "";
		return String(name).trim() || null;
	}

	// Mentions arrive as "@" and a number; show the person's name instead.
	function withMentionNames(m, text) {
		const list = m.mentionedJidList || [];
		if (!text || !list.length) {
			return text;
		}
		let out = text;
		for (const wid of list) {
			const name = personName(collections().Contact.get(wid));
			if (name && wid.user) {
				out = out.split("@" + wid.user).join("@" + name);
			}
		}
		return out;
	}

	function senderName(m) {
		if (m.id.fromMe) {
			return null;
		}
		return personName(m.senderObj) || m.notifyName || null;
	}

	// In a personal chat WhatsApp may not know a sender object; the chat's name is the other person's name.
	function remoteTitle(m) {
		try {
			const chat = m.id.remote && collections().Chat.get(m.id.remote);
			return chat && !isGroupChat(chat) ? chatTitle(chat) : null;
		} catch (e) {
			return null;
		}
	}

	// The reactions on a message: each emoji, how many people chose it, and whether the user did.
	// WhatsApp keeps them by message id; they are loaded when the chat is opened in its view.
	function reactionSummary(model) {
		try {
			const list = model && model.reactions;
			const items = list ? (list.getModelsArray ? list.getModelsArray() : Array.from(list)) : [];
			return items
				.map((r) => {
					const senders = r.senders;
					const count = senders ? (typeof senders.length === "number" ? senders.length : 0) : 0;
					return { emoji: r.aggregateEmoji || String(r.id || ""), count: count, mine: !!r.hasReactionByMe };
				})
				.filter((r) => r.emoji && r.count > 0);
		} catch (e) {
			return [];
		}
	}

	function reactionsOf(m) {
		try {
			if (m.id.remote && m.id.remote.server === "newsletter") {
				return channelReactions(m);
			}
			return reactionSummary(collections().Reactions.get(m.id));
		} catch (e) {
			return [];
		}
	}

	const MEDIA_TYPES = new Set(["image", "video", "document", "ptt", "audio", "sticker", "ptv"]);

	function messageInfo(m) {
		const type = m.type;
		const info = {
			id: msgId(m),
			chatId: m.id.remote && m.id.remote._serialized,
			fromMe: !!m.id.fromMe,
			type: type,
			t: m.t || 0,
			sender: senderName(m) || (m.id.fromMe ? null : remoteTitle(m)),
			ack: typeof m.ack === "number" ? m.ack : null,
			text: "",
			caption: "",
			filename: "",
			duration: m.duration ? Number(m.duration) || 0 : 0,
			isForwarded: !!m.isForwarded,
			starred: !!m.star,
			reactions: reactionsOf(m),
		};
		if (type === "chat") {
			info.text = withMentionNames(m, m.body || "");
		} else if (MEDIA_TYPES.has(type)) {
			// For media, body holds a thumbnail, not text.
			info.caption = withMentionNames(m, m.caption || "");
			info.filename = m.filename || "";
		} else if (type === "location") {
			info.text = m.loc || "";
		} else if (type === "vcard") {
			info.text = m.vcardFormattedName || "";
		} else if (type === "poll_creation") {
			info.text = m.pollName || "";
			info.poll = {
				options: (m.pollOptions || []).length,
				multiple: (m.pollSelectableOptionsCount || 0) !== 1,
				votes: pollVotes(m).length,
			};
		}
		if (m.isViewOnce) {
			info.viewOnce = true;
		}
		if (m.latestEditMsgKey) {
			info.edited = true;
		}
		try {
			const pin = req("WAWebPinInChatCollection").PinInChatCollection.getByParentMsgKey(m.id);
			info.pinned = !!(pin && req("WAWebPinInChatCollection").isPinValid(pin));
		} catch (e) {}
		if (type === "event_creation") {
			info.text = m.eventName || "";
			info.event = {
				start: m.eventStartTime || 0,
				canceled: !!m.isEventCanceled,
			};
		}
		if (!info.text && !info.caption && !MEDIA_TYPES.has(type) && type !== "chat") {
			try {
				info.text = String(req("WAWebFormatMsgText")({ msg: m }) || "");
			} catch (e) {
				// Left empty: the add-on names the type instead.
			}
		}
		if (m.quotedMsg) {
			try {
				// The quote is plain data without an id; who wrote it is in quotedParticipant.
				const q = m.quotedMsg;
				const author = m.quotedParticipant ? String(m.quotedParticipant) : "";
				const fromMe = q.id ? !!q.id.fromMe : !!author && myIdSet().has(author);
				info.quoted = {
					text: q.type === "chat" ? q.body || "" : q.caption || "",
					type: q.type,
					sender: fromMe ? null : author ? contactName(author) : remoteTitle(m),
					fromMe: fromMe,
				};
			} catch (e) {
				// A quote that cannot be read is left out.
			}
		}
		return info;
	}

	// A channel post's reactions are counts only: channels do not say who reacted.
	function channelReactions(m) {
		const r = req("WAWebNewsletterReactionCollection").NewsletterMessageReactionsCollection.get(m.id);
		return r && r.reactionCountMap
			? [...r.reactionCountMap].map(([emoji, count]) => ({ emoji: emoji, count: count, mine: r.myReaction === emoji }))
			: [];
	}

	function chatInfo(chat) {
		const msgs = chat.msgs ? chat.msgs.getModelsArray() : [];
		let last = null;
		for (let i = msgs.length - 1; i >= 0; i--) {
			if (!msgs[i].isNotification && !HIDDEN_TYPES.has(msgs[i].type)) {
				last = messageInfo(msgs[i]);
				break;
			}
		}
		const info = {
			id: chat.id._serialized || chat.id.toString(),
			title: chatTitle(chat),
			isGroup: isGroupChat(chat),
			unread: Math.max(0, chat.unreadCount || 0),
			t: chat.t || 0,
			pinned: !!chat.pin,
			archived: !!chat.archive,
			muted: !!(chat.mute && chat.mute.isMuted),
			favorite: !!chat.isFavorite,
			last: last,
			disappearing: 0,
			ongoingCall: false,
		};
		if (isGroupChat(chat)) {
			try {
				info.ongoingCall = !!req("WAWebVoipOngoingCallCollection").WAWebVoipOngoingCallCollection.getByChat(chat);
			} catch (e) {}
		}
		try {
			// Seconds after which new messages disappear, when someone turned that on; 0 when off.
			info.disappearing = Number(chat.ephemeralDuration) || 0;
		} catch (e) {}
		if (chat.id.server === "newsletter") {
			const md = chat.newsletterMetadata || {};
			const expiry = chat.muteExpiration || 0;
			info.isChannel = true;
			info.title = chat.name || md.name || "";
			info.muted = expiry === -1 || expiry * 1000 > Date.now();
			info.canPost = md.membershipType === "admin" || md.membershipType === "owner";
			info.followers = md.size || 0;
			info.verified = !!md.verified;
		} else if (chat.groupType && chat.groupType !== "DEFAULT") {
			info.groupType = String(chat.groupType);
		}
		return info;
	}

	function chats(options) {
		const archived = !!(options && options.archived);
		return collections()
			.Chat.getModelsArray()
			.filter((c) => isListedChat(c) && !!c.archive === archived)
			.sort((a, b) => (b.pin || 0) - (a.pin || 0) || (b.t || 0) - (a.t || 0))
			.map(chatInfo);
	}

	// Messages -------------------------------------------------------------------------------------------

	const HIDDEN_TYPES = new Set(["e2e_notification", "notification_template", "gp2", "protocol", "ciphertext"]);

	function visibleMessages(chat) {
		return chat.msgs.getModelsArray().filter((m) => !HIDDEN_TYPES.has(m.type) && !m.isNotification);
	}

	async function loadEarlierOnce(chat) {
		const before = chat.msgs.length;
		try {
			await req("WAWebChatLoadMessages").loadEarlierMsgs({ chat: chat });
		} catch (e) {
			return 0;
		}
		return chat.msgs.length - before;
	}

	async function messages(chatId, count) {
		const chat = getChat(chatId);
		for (let i = 0; i < 4 && visibleMessages(chat).length < count; i++) {
			if ((await loadEarlierOnce(chat)) === 0) {
				break;
			}
		}
		return visibleMessages(chat).slice(-count).map(messageInfo);
	}

	async function loadEarlier(chatId, beforeId) {
		const chat = getChat(chatId);
		await loadEarlierOnce(chat);
		const all = visibleMessages(chat);
		const index = all.findIndex((m) => msgId(m) === beforeId);
		return (index >= 0 ? all.slice(0, index) : []).map(messageInfo);
	}

	// The user's own ids: WhatsApp knows the user by a phone number id and a newer "lid".
	function myIdSet() {
		const me = req("WAWebUserPrefsMeUser");
		const ids = new Set();
		for (const getter of ["getMaybeMeLidUser", "getMaybeMePnUser"]) {
			try {
				const wid = me[getter]();
				if (wid) {
					ids.add(wid.toString());
				}
			} catch (e) {
				// Older or newer WhatsApp versions may lack one of these.
			}
		}
		return ids;
	}

	// The people in a group, for @mentions. The user is left out.
	function participants(chatId) {
		const chat = getChat(chatId);
		if (!isGroupChat(chat) || !chat.groupMetadata) {
			return [];
		}
		const C = collections();
		const myIds = myIdSet();
		return chat.groupMetadata.participants
			.getModelsArray()
			.map((p) => {
				const contact = C.Contact.get(p.id);
				return {
					id: p.id.toString(),
					name: personName(contact) || p.id.user,
					pushname: (contact && contact.pushname) || "",
					isAdmin: !!(p.isAdmin || p.isSuperAdmin),
					isMe: myIds.has(p.id.toString()) || !!(contact && contact.isMe),
				};
			})
			.filter((p) => !p.isMe)
			.sort((a, b) => a.name.localeCompare(b.name));
	}

	// Emoji by name, for ":grin" in the message box: WhatsApp's own emoji search, which puts the user's
	// recent emoji first. Its names are English; WhatsApp has none in Indonesian.
	const EMOJI_DICTIONARY = "WAWebLocalesCldrEmojiSuggestionEn";
	let emojiTrie = null;

	async function emojiSuggestions(query, limit) {
		if (!emojiTrie) {
			let dictionary;
			try {
				dictionary = req(EMOJI_DICTIONARY);
			} catch (e) {
				// WhatsApp loads it the first time its emoji panel is searched.
				dictionary = await req("JSResource")(EMOJI_DICTIONARY).load();
			}
			emojiTrie = await req("WAWebEmojiSearch").emojiLocaleDictsToTrie([dictionary.default || dictionary]);
		}
		return req("WAWebEmojiSearch")
			.emojiSearch(String(query || ""), emojiTrie)
			.slice(0, limit || 20);
	}

	async function sendText(chatId, text, quotedId, mentions) {
		if (typeof text !== "string" || !text.trim()) {
			throw new Error("emptyMessage");
		}
		const chat = getChat(chatId);
		const options = quotedId ? { quotedMsg: getMsg(quotedId) } : {};
		if (mentions && mentions.length && chat.groupMetadata) {
			// The add-on shows "@Name"; WhatsApp sends "@" and the person's number, with their ids.
			const wids = [];
			for (const mention of mentions) {
				const participant = chat.groupMetadata.participants
					.getModelsArray()
					.find((p) => p.id.toString() === mention.id);
				if (participant && text.includes("@" + mention.name)) {
					text = text.split("@" + mention.name).join("@" + participant.id.user);
					wids.push(participant.id);
				}
			}
			if (wids.length) {
				options.mentionedJidList = wids;
			}
		}
		const result = await req("WAWebSendTextMsgChatAction").sendTextMsgToChat(chat, text, options);
		const status = result && result.messageSendResult;
		if (status && status !== "OK") {
			throw new Error("sendFailed:" + status);
		}
		return true;
	}

	// Marks the chat read and sends read receipts, as opening it in WhatsApp does. WhatsApp normally waits
	// until its page is being looked at ("afterAvailable"); the add-on's user reads it here instead, with
	// the browser in the background, so it is sent now. It is sent even when WhatsApp's count is already
	// zero, since opening the chat in WhatsApp's view can clear the count without sending the receipt.
	async function markSeen(chatId) {
		const chat = getChat(chatId);
		await req("WAWebUpdateUnreadChatAction").sendSeen({ chat: chat, threadId: undefined, afterAvailable: false });
		return true;
	}

	// Polls ----------------------------------------------------------------------------------------------

	// The latest vote of each person on a poll. WhatsApp loads them when the chat is opened in its view.
	function pollVotes(m) {
		try {
			const key = req("WAWebReferentialMsgKey").getReferentialMsgKey(m);
			const votes = req("WAWebPollsPollVoteCollection").PollVoteCollection.getForParentAddressingModeInsensitive([key])[0];
			return votes ? votes.getModelsArray().filter((v) => (v.selectedOptionLocalIds || []).length) : [];
		} catch (e) {
			return [];
		}
	}

	function pollInfo(messageId) {
		const m = getMsg(messageId);
		if (m.type !== "poll_creation") {
			throw new Error("notAPoll");
		}
		const myIds = myIdSet();
		const getters = req("WAWebFrontendPollVoteGetters");
		const options = (m.pollOptions || []).map((o) => ({ id: o.localId, name: o.name, voters: [], mine: false }));
		const byId = new Map(options.map((o) => [o.id, o]));
		const votes = pollVotes(m);
		for (const vote of votes) {
			const sender = String(vote.sender || "");
			const isMe = myIds.has(sender);
			let name = null;
			try {
				name = personName(getters.getSenderObj(vote));
			} catch (e) {
				// Fall back to the number below.
			}
			for (const id of vote.selectedOptionLocalIds || []) {
				const option = byId.get(id);
				if (!option) {
					continue;
				}
				if (isMe) {
					option.mine = true;
				} else {
					option.voters.push(name || sender.split("@")[0]);
				}
			}
		}
		return {
			id: messageId,
			question: m.pollName || "",
			multiple: (m.pollSelectableOptionsCount || 0) !== 1,
			voters: votes.length,
			options: options,
		};
	}

	// Sends the user's choice. An empty choice takes the user's vote back, as in WhatsApp.
	async function vote(messageId, optionIds) {
		const m = getMsg(messageId);
		if (m.type !== "poll_creation") {
			throw new Error("notAPoll");
		}
		const valid = new Set((m.pollOptions || []).map((o) => o.localId));
		const chosen = (optionIds || []).filter((id) => valid.has(id));
		if ((m.pollSelectableOptionsCount || 0) === 1 && chosen.length > 1) {
			throw new Error("oneOptionOnly");
		}
		await req("WAWebPollsSendVoteMsgAction").sendVote(m, new Set(chosen));
		return true;
	}

	// Opens the chat in WhatsApp's own view too, as the user would. WhatsApp then loads what it shows
	// with the messages, such as poll votes and reactions.
	async function openInWhatsApp(chatId) {
		const chat = getChat(chatId);
		try {
			await req("WAWebCmd").Cmd.openChatBottom({ chat: chat });
			return true;
		} catch (e) {
			return false;
		}
	}

	// Typing, forwarding, message info, new chats and search -----------------------------------------

	// Tells the other person the user is typing ("composing"), recording, or stopped ("paused").
	async function setTyping(chatId, state) {
		const chat = getChat(chatId);
		const presence = req("WAWebPresenceChatAction");
		if (state === "composing") {
			await presence.markComposing(chat);
		} else if (state === "recording") {
			await presence.markRecording(chat);
		} else {
			await presence.markPaused(chat);
		}
		return true;
	}

	async function forward(messageIds, chatIds) {
		await req("WAWebForwardMessageFlowLoadable").requireBundle();
		const msgs = messageIds.map(getMsg);
		const chats = chatIds.map(getChat);
		await req("WAWebForwardMessagesToChat").forwardMessagesToChats({
			msgs: msgs,
			chats: chats,
			includeCaption: true,
		});
		return true;
	}

	// Who received, read and played one of the user's messages, with times.
	async function messageReceipts(messageId) {
		const m = getMsg(messageId);
		if (!m.id.fromMe) {
			throw new Error("notMine");
		}
		const C = collections();
		const list = (people) =>
			(people && people.getModelsArray ? people.getModelsArray() : [])
				.map((p) => ({ name: personName(C.Contact.get(p.id)) || String((p.id && p.id.user) || p.id), t: p.t || 0 }))
				.sort((a, b) => a.t - b.t);
		let info = null;
		try {
			info = await C.MsgInfo.find(m.id);
		} catch (e) {
			// Personal chats may have no per-person info; the message's state still says enough.
		}
		return {
			ack: typeof m.ack === "number" ? m.ack : 0,
			t: m.t || 0,
			delivered: list(info && info.delivery),
			read: list(info && info.read),
			played: list(info && info.played),
			deliveryRemaining: (info && info.deliveryRemaining) || 0,
			readRemaining: (info && info.readRemaining) || 0,
		};
	}

	// A chat with a phone number, made if it does not exist yet, as WhatsApp's "new chat" does.
	async function chatWithNumber(phone) {
		const digits = String(phone || "").replace(/[^0-9]/g, "");
		if (digits.length < 6) {
			throw new Error("badNumber");
		}
		const wid = req("WAWebWidFactory").createWid(digits + "@c.us");
		const found = await req("WAWebQueryExistsJob").queryWidExists(wid);
		if (!found || !found.wid) {
			throw new Error("notOnWhatsApp");
		}
		const result = await req("WAWebFindChatAction").findOrCreateLatestChat(found.wid);
		const chat = (result && result.chat) || result;
		if (!chat || !chat.id) {
			throw new Error("notOnWhatsApp");
		}
		return chatInfo(chat);
	}

	// Messages in a chat whose text contains the query, loading older ones as WhatsApp's search would.
	async function searchMessages(chatId, query, batches) {
		const chat = getChat(chatId);
		const needle = String(query || "").toLowerCase();
		if (!needle) {
			return [];
		}
		for (let i = 0; i < (batches || 10); i++) {
			if ((await loadEarlierOnce(chat)) === 0) {
				break;
			}
		}
		return visibleMessages(chat)
			.filter((m) => {
				const text = (m.type === "chat" ? m.body : m.caption) || "";
				return text.toLowerCase().includes(needle) || (m.filename || "").toLowerCase().includes(needle);
			})
			.map(messageInfo);
	}

	// Every loaded message of a chat, after a search loaded older ones.
	function allMessages(chatId) {
		return visibleMessages(getChat(chatId)).map(messageInfo);
	}

	// Message and chat actions, as in WhatsApp's menus ---------------------------------------------------

	function messageActions(messageId) {
		const m = getMsg(messageId);
		const cap = req("WAWebMsgActionCapability");
		const check = (name) => {
			try {
				return !!cap[name](m);
			} catch (e) {
				return false;
			}
		};
		return {
			star: check("canStarMsg"),
			starred: !!m.star,
			edit: !!m.id.fromMe && m.type === "chat" && check("canEditText"),
			// Why it cannot be edited: not the user's, not text, or too late, as WhatsApp allows a while only.
			editBlocked: !m.id.fromMe ? "notMine" : m.type !== "chat" ? "notText" : check("canEditText") ? "" : "tooLate",
			deleteForMe: true,
			deleteForEveryone: check("canSenderRevokeMsg") || check("canAdminRevokeMsg"),
			react: m.type !== "revoked" && m.type !== "call_log",
			text: m.type === "chat" ? m.body || "" : m.caption || "",
			reactions: reactionsOf(m),
		};
	}

	// The reactions, asking WhatsApp to look them up if they are not loaded yet.
	async function reactions(messageId) {
		const m = getMsg(messageId);
		try {
			const model = await collections().Reactions.find(m.id);
			const found = reactionSummary(model);
			if (found.length) {
				return found;
			}
		} catch (e) {
			// Fall back to what is loaded.
		}
		return reactionsOf(m);
	}

	async function react(messageId, emoji) {
		await req("WAWebSendReactionMsgAction").sendReactionToMsg(getMsg(messageId), emoji || "");
		return true;
	}

	function star(messageId, starred) {
		const m = getMsg(messageId);
		const chat = getChat(m.id.remote._serialized);
		const Cmd = req("WAWebCmd").Cmd;
		if (starred) {
			Cmd.sendStarMsgs(chat, [m], false);
		} else {
			Cmd.sendUnstarMsgs(chat, [m], false);
		}
		return true;
	}

	async function editText(messageId, text) {
		if (typeof text !== "string" || !text.trim()) {
			throw new Error("emptyMessage");
		}
		await req("WAWebSendMessageEditAction").sendMessageEdit(getMsg(messageId), text, {});
		return true;
	}

	function deleteMessage(messageId, forEveryone) {
		const m = getMsg(messageId);
		const chat = getChat(m.id.remote._serialized);
		const Cmd = req("WAWebCmd").Cmd;
		if (forEveryone) {
			if (!messageActions(messageId).deleteForEveryone) {
				throw new Error("cannotRevoke");
			}
			Cmd.sendRevokeMsgs(chat, { list: [m], type: "message" }, { clearMedia: true });
		} else {
			Cmd.sendDeleteMsgs(chat, { list: [m], type: "message" }, true);
		}
		return true;
	}

	// Several messages at once, as WhatsApp's "Select messages" does. They are grouped by chat.
	function byChat(messageIds) {
		const groups = new Map();
		for (const messageId of messageIds) {
			const m = getMsg(messageId);
			const chatId = m.id.remote._serialized;
			if (!groups.has(chatId)) {
				groups.set(chatId, []);
			}
			groups.get(chatId).push(m);
		}
		return groups;
	}

	// What can be done with all of them: delete for everyone only if every one may be.
	function messagesActions(messageIds) {
		const all = messageIds.map((id) => messageActions(id));
		return {
			deleteForEveryone: all.length > 0 && all.every((a) => a.deleteForEveryone),
			star: all.some((a) => a.star),
			allStarred: all.length > 0 && all.every((a) => a.starred || !a.star),
		};
	}

	function deleteMessages(messageIds, forEveryone) {
		const Cmd = req("WAWebCmd").Cmd;
		if (forEveryone && !messagesActions(messageIds).deleteForEveryone) {
			throw new Error("cannotRevoke");
		}
		for (const [chatId, msgs] of byChat(messageIds)) {
			const chat = getChat(chatId);
			if (forEveryone) {
				Cmd.sendRevokeMsgs(chat, { list: msgs, type: "message" }, { clearMedia: true });
			} else {
				Cmd.sendDeleteMsgs(chat, { list: msgs, type: "message" }, true);
			}
		}
		return true;
	}

	function starMessages(messageIds, starred) {
		const Cmd = req("WAWebCmd").Cmd;
		for (const [chatId, msgs] of byChat(messageIds)) {
			const chat = getChat(chatId);
			if (starred) {
				Cmd.sendStarMsgs(chat, msgs, false);
			} else {
				Cmd.sendUnstarMsgs(chat, msgs, false);
			}
		}
		return true;
	}

	// Several chats at once. A group the user is still in is left alone: WhatsApp asks to exit it first.
	async function chatsAction(chatIds, action, seconds) {
		let done = 0;
		let skipped = 0;
		for (const chatId of chatIds) {
			if (action === "delete") {
				const chat = getChat(chatId);
				if (isGroupChat(chat) && !chat.isReadOnly) {
					skipped++;
					continue;
				}
				await req("WAWebDeleteChatAction").sendDelete(chat);
			} else {
				await chatAction(chatId, action, seconds);
			}
			done++;
		}
		return { done: done, skipped: skipped };
	}

	// Starred messages, channels and communities ------------------------------------------------------

	// All starred messages, newest first; WhatsApp loads them 50 at a time from its database.
	async function starredMessages() {
		const starred = collections().StarredMsg;
		for (let i = 0; i < 40 && !starred.isSynced; i++) {
			const before = starred.length;
			await starred.sync();
			if (starred.length === before) {
				break;
			}
		}
		return starred.getModelsArray().map((m) => {
			const info = messageInfo(m);
			const chat = req("WAWebFrontendMsgGetters").getChat(m);
			info.chatTitle = chat ? chatTitle(chat) : "";
			return info;
		});
	}

	const FOLLOWING = new Set(["subscriber", "admin", "owner"]);

	// The channels the user follows. A directory search adds others as guests, which are left out.
	function channels() {
		const list = collections().WAWebNewsletterCollection;
		return (list ? list.getModelsArray() : [])
			.filter((n) => FOLLOWING.has(n.newsletterMetadata && n.newsletterMetadata.membershipType))
			.sort((a, b) => (b.t || 0) - (a.t || 0))
			.map(chatInfo);
	}

	async function searchChannels(text) {
		const found = await req("WAWebNewsletterDirectorySearchAction").fetchNewsletterDirectories({
			searchText: String(text || ""),
			categories: [],
			countryCodes: [],
			cursorToken: undefined,
			skipSubscribedNewsletters: false,
			view: undefined,
		});
		return (found.newsletters || []).map((n) => {
			const info = chatInfo(n);
			const md = n.newsletterMetadata || {};
			info.following = FOLLOWING.has(md.membershipType);
			info.description = md.description || "";
			return info;
		});
	}

	async function followChannel(channelId, follow) {
		const channel = getChat(channelId);
		if (follow) {
			await req("WAWebFollowNewsletter").followNewsletter(channel, {});
		} else {
			await req("WAWebNewsletterUnsubscribeAction").unsubscribeFromNewsletterAction(channel, {
				eventSurface: req("WAWebWamEnumChannelEventSurface").CHANNEL_EVENT_SURFACE.CHANNEL_PROFILE,
				discoverySurface: req("WAWebWamEnumTsSurface").TS_SURFACE.CHANNEL_PROFILE,
			});
		}
		return true;
	}

	function groupKind(metadata) {
		try {
			return String(req("WAWebGroupMetadataGetters").getGroupType(metadata) || "DEFAULT");
		} catch (e) {
			return "DEFAULT";
		}
	}

	// The user's communities, each with its announcement group, the groups the user is in, and the
	// others they could join.
	async function communities() {
		const C = collections();
		const metadata = C.WAWebGroupMetadataCollection;
		const unjoined = C.WAWebUnjoinedSubgroupMetadataCollection;
		const result = [];
		for (const parent of metadata.getModelsArray().filter((g) => g.isParentGroup)) {
			try {
				await req("WAWebQuerySubGroupAction").queryAndUpdateSubgroupsMetadata(parent.id, parent.joinedSubgroups);
			} catch (e) {
				// The groups already known are shown.
			}
			const joined = (parent.joinedSubgroups || []).map((id) => metadata.get(id)).filter(Boolean);
			const groupInfo = (g) => {
				const chat = C.Chat.get(g.id);
				const info = chat ? chatInfo(chat) : { id: g.id.toString(), title: g.subject || "", unread: 0 };
				info.announcement = !!g.defaultSubgroup || groupKind(g) === "LINKED_ANNOUNCEMENT_GROUP";
				info.joined = true;
				return info;
			};
			const others = unjoined
				? unjoined
						.getModelsArray()
						.filter((u) => u.parentGroupId && u.parentGroupId.equals(parent.id))
						.map((u) => ({
							id: u.id.toString(),
							title: u.subject || "",
							announcement: !!u.defaultSubgroup,
							joined: false,
							size: u.size || 0,
							needsApproval: !!u.membershipApprovalMode,
							requested: !!u.membershipApprovalRequest,
						}))
				: [];
			const groups = joined.map(groupInfo).concat(others);
			groups.sort((a, b) => Number(b.announcement) - Number(a.announcement));
			result.push({
				id: parent.id.toString(),
				title: parent.subject || "",
				description: parent.desc || "",
				groups: groups,
				unread: groups.reduce((sum, g) => sum + (g.unread || 0), 0),
			});
		}
		return result;
	}

	// Joins a group of a community, or asks to when its admins approve new members.
	async function joinCommunityGroup(communityId, groupId) {
		const wf = req("WAWebWidFactory");
		const parent = wf.createWid(communityId);
		const group = wf.createWid(groupId);
		try {
			await req("JSResourceForInteraction")("WAWebSubgroupJoinModal.react").load();
		} catch (e) {
			// Already loaded, or loaded differently; the join below says if it is missing.
		}
		const join = req("WAWebJoinSubgroupAction");
		const info = await req("WAWebQuerySubGroupAction").querySubgroupInfo(group, parent);
		if (info && info.defaultSubgroup && join.joinAnnouncementGroup) {
			await join.joinAnnouncementGroup(parent, group);
			return "joined";
		}
		const request = !!(info && info.membershipApprovalMode);
		try {
			await join.joinSubgroup({ parentGroupId: parent, subgroupId: group, request: request });
		} catch (e) {
			if (e && e.membershipApprovalMode) {
				await join.joinSubgroup({ parentGroupId: parent, subgroupId: group, request: true });
				return "requested";
			}
			throw e;
		}
		return request ? "requested" : "joined";
	}

	// Groups and chats: what WhatsApp's chat and group info offer -------------------------------------

	function serverError(e) {
		const status = e && (e.status || e.statusCode);
		return new Error(status ? "server" + status : (e && e.message) || "failed");
	}

	// What the user may do in a chat, for its More options and info.
	function chatAbilities(chatId) {
		const chat = getChat(chatId);
		const result = {
			isGroup: isGroupChat(chat),
			isChannel: chat.id.server === "newsletter",
			favoritesEnabled: false,
			favorite: !!chat.isFavorite,
			ephemeral: 0,
			canSetEphemeral: false,
			blocked: false,
		};
		try {
			result.favoritesEnabled = !!req("WAWebInboxFiltersGatingUtils").inboxFavoritesEnabled();
		} catch (e) {}
		try {
			result.ephemeral = chat.ephemeralDuration || 0;
			result.canSetEphemeral = !!req("WAWebChatEphemerality").shouldShowEphemeralSetting(chat);
		} catch (e) {}
		if (!result.isGroup && chat.contact) {
			result.blocked = !!chat.contact.isContactBlocked;
		}
		const gm = chat.groupMetadata;
		if (result.isGroup && gm) {
			const people = gm.participants;
			const ask = (f) => {
				try {
					return !!f();
				} catch (e) {
					return false;
				}
			};
			Object.assign(result, {
				member: ask(() => people.iAmMember()),
				admin: ask(() => people.iAmAdmin()),
				canAdd: ask(() => people.canAdd()),
				canSetSubject: ask(() => gm.canSetSubject()),
				canSetDescription: ask(() => gm.canSetDescription()),
				canSetSettings: ask(() => gm.canSetGroupProperty()),
				announce: !!gm.announce,
				restrict: !!gm.restrict,
				approval: !!gm.membershipApprovalMode,
				memberAdd: String(gm.memberAddMode || "") === "all_member_add",
				readOnly: !!chat.isReadOnly,
				groupType: groupKind(gm),
			});
		}
		return result;
	}

	function contactsOf(ids) {
		const C = collections();
		return ids.map((id) => C.Contact.get(id)).filter(Boolean);
	}

	// Contacts to choose from when making a group or adding people: saved contacts with WhatsApp.
	function contactChoices() {
		return collections()
			.Contact.getModelsArray()
			.filter((c) => c.id && c.id.server === "c.us" && c.name && !c.isMe && !c.isBot)
			.map((c) => ({ id: c.id.toString(), title: personName(c) || c.id.user }))
			.sort((a, b) => a.title.localeCompare(b.title));
	}

	async function createGroup(title, contactIds) {
		await req("WAWebNewGroupFlowLoadable").requireBundle();
		const result = await req("WAWebCreateGroupAction").createGroup(
			{
				title: String(title),
				ephemeralDuration: 0,
				restrict: true,
				announce: true,
				membershipApprovalMode: false,
				memberAddMode: true,
				memberShareGroupHistoryMode: true,
			},
			contactsOf(contactIds),
			[],
			req("WAWebWamEnumGroupCreateEntryPoint").GROUP_CREATE_ENTRY_POINT.MENU
		);
		if (!result) {
			throw new Error("createFailed");
		}
		return {
			chatId: result.gid.toString(),
			failed: (result.participants || []).filter((x) => String(x.code) !== "200").length,
		};
	}

	function participantModels(chat, ids) {
		const people = chat.groupMetadata.participants;
		return ids.map((id) => people.get(id)).filter(Boolean);
	}

	// add, remove, promote or demote. Returns how many could not be done, such as people whose privacy
	// asks for an invite instead (WhatsApp then offers to send them one).
	async function changeParticipants(chatId, action, ids) {
		const chat = getChat(chatId);
		const M = req("WAWebModifyParticipantsGroupAction");
		try {
			if (action === "add") {
				const result = await M.addParticipants(
					chat,
					contactsOf(ids),
					[],
					req("WAWebWamEnumAddMembersEntrypointType").ADD_MEMBERS_ENTRYPOINT_TYPE.GROUP_INFO_ACTION_BUTTON
				);
				return ((result && result.participants) || []).filter((x) => String(x.code) !== "200").length;
			}
			const models = participantModels(chat, ids);
			if (action === "remove") {
				await M.removeParticipants(chat, models);
			} else if (action === "promote") {
				await M.promoteParticipants(chat, models);
			} else if (action === "demote") {
				await M.demoteParticipants(chat, models);
			}
			return 0;
		} catch (e) {
			throw serverError(e);
		}
	}

	async function setGroupInfo(chatId, field, value) {
		const chat = getChat(chatId);
		if (field === "subject") {
			await req("WAWebSetSubjectGroupAction").setGroupSubject(chat, String(value));
		} else if (field === "description") {
			await req("WAWebSetDescAction").setDesc(chat, String(value));
		}
		return true;
	}

	// announcement, restrict, membership_approval_mode or member_add_mode, on (1) or off (0).
	async function setGroupSetting(chatId, type, on) {
		const result = await req("WAWebSetPropertyGroupAction").setGroupProperty(getChat(chatId), type, on ? 1 : 0);
		if (result && result.name && result.name !== "SetPropertyResponseSuccess") {
			throw new Error("settingFailed");
		}
		return true;
	}

	async function inviteLink(chatId, reset) {
		const gm = getChat(chatId).groupMetadata;
		const invites = req("WAWebGroupInviteAction");
		try {
			if (reset) {
				await invites.revokeGroupInvite(gm);
			} else {
				await invites.queryGroupInviteCode(gm);
			}
		} catch (e) {
			throw serverError(e);
		}
		return gm.inviteCode ? "https://chat.whatsapp.com/" + gm.inviteCode : "";
	}

	async function exitGroup(chatId, andDelete) {
		const chat = getChat(chatId);
		const left = await req("WAWebExitGroupAction").sendExitGroup(chat);
		if (!left) {
			throw new Error("exitFailed");
		}
		if (andDelete) {
			await req("WAWebDeleteChatAction").sendDelete(chat);
		}
		return true;
	}

	async function deleteChat(chatId) {
		await req("WAWebDeleteChatAction").sendDelete(getChat(chatId));
		return true;
	}

	async function clearChat(chatId, keepStarred) {
		await req("WAWebSendClearChatAction").sendClear(getChat(chatId), !!keepStarred);
		return true;
	}

	async function setBlocked(chatId, blocked) {
		const contact = getChat(chatId).contact;
		const B = req("WAWebBlockContactAction");
		if (blocked) {
			await B.blockContact({ contact: contact, blockEntryPoint: "chat" });
		} else {
			await B.unblockContact(contact, "chat");
		}
		return true;
	}

	// Reports a chat to WhatsApp, as its Report dialog does; a group is left first, a person can be
	// blocked as well.
	async function reportChat(chatId, alsoBlockOrExit) {
		const chat = getChat(chatId);
		const S = req("WAWebSendSpamChatAction");
		if (isGroupChat(chat)) {
			const spamFlow = "group_info_report";
			if (alsoBlockOrExit) {
				const left = await req("WAWebExitGroupAction").sendExitGroup(chat);
				if (!left) {
					throw new Error("exitFailed");
				}
			}
			await S.sendReport({ chat: chat, spamFlow: spamFlow });
		} else if (alsoBlockOrExit) {
			await S.sendReportBlock({ chat: chat, spamFlow: "account_info_report" });
		} else {
			await S.sendReport({ chat: chat, spamFlow: "account_info_report" });
		}
		return true;
	}

	const EPHEMERAL_DURATIONS = [0, 86400, 604800, 7776000];

	async function setDisappearing(chatId, seconds) {
		const duration = Number(seconds) || 0;
		if (!EPHEMERAL_DURATIONS.includes(duration)) {
			throw new Error("badDuration");
		}
		await req("WAWebChangeEphemeralDurationChatAction").changeEphemeralDuration(
			getChat(chatId),
			duration,
			req("WAWebWamEnumEphemeralSettingEntryPointType").EPHEMERAL_SETTING_ENTRY_POINT_TYPE.CHAT_INFO,
			req("WAWebEphemeralityTypes").DisappearingModeTrigger.ChatSettings
		);
		return true;
	}

	async function setFavorite(chatId, favorite) {
		const chat = getChat(chatId);
		const options = { entryPoint: 3, suppressToast: true };
		if (favorite) {
			await req("WAWebAddToFavoritesAction").addToFavoritesAction([chat.id], options);
		} else {
			await req("WAWebRemoveFromFavoritesAction").removeFromFavoritesAction([chat.id], options);
		}
		return true;
	}

	// More for messages: polls, pins, private replies, contacts, stickers, search, media ---------------

	async function loadBundle(name) {
		try {
			await req("JSResourceForInteraction")(name).load();
		} catch (e) {
			// Already loaded, or loaded another way.
		}
	}

	async function sendPoll(chatId, question, options, single) {
		try {
			await req("JSResourceForInteraction")("WAWebPollsCreatePollModal")
				.__setRef("WAWebPollsCreatePollModalLoadable.react")
				.load();
		} catch (e) {}
		await req("WAWebPollsSendPollCreationMsgAction").sendPollCreation({
			chat: getChat(chatId),
			poll: {
				name: String(question),
				options: options.map((name) => ({ name: String(name) })),
				selectableOptionsCount: single ? 1 : 0,
				contentType: "TEXT",
				pollType: "POLL",
				endTime: undefined,
				hideVoterNames: undefined,
			},
		});
		return true;
	}

	const PIN_DURATIONS = { day: "OneDay", week: "SevenDays", month: "ThirtyDays" };

	// Pins a message for everyone for a day, a week or a month, or unpins it. When the chat already has
	// as many pins as WhatsApp allows, the oldest is unpinned first, as WhatsApp does.
	async function pinMessage(messageId, duration) {
		const m = getMsg(messageId);
		const T = req("WAWebProtobufsE2E.pb").Message$PinInChatMessage$Type;
		const send = req("WAWebSendPinMessageAction").sendPinInChatMsg;
		if (!duration) {
			await send({ msg: m, pinType: T.UNPIN_FOR_ALL });
			return true;
		}
		if (!req("WAWebMsgActionCapability").canPinMsg(m)) {
			throw new Error("cannotPin");
		}
		const pins = pinnedOf(m.id.remote.toString());
		if (pins.length >= req("WAWebPinMsgGatingUtils").getMaxPins()) {
			const oldest = collections().Msg.get(pins[0].parentKey);
			if (oldest) {
				await send({ msg: oldest, pinType: T.UNPIN_FOR_ALL });
			}
		}
		await send({ msg: m, pinType: T.PIN_FOR_ALL, pinExpiryDurationOption: PIN_DURATIONS[duration] || "SevenDays" });
		return true;
	}

	function pinnedOf(chatId) {
		const P = req("WAWebPinInChatCollection");
		const C = collections();
		return P.PinInChatCollection.getModelsArray()
			.filter((p) => String(p.chatId) === chatId && P.isPinValid(p))
			.map((p) => ({ parentKey: p.parentMsgKey, msg: C.Msg.get(p.parentMsgKey) }))
			.sort((a, b) => ((a.msg && a.msg.t) || 0) - ((b.msg && b.msg.t) || 0));
	}

	function pinnedMessages(chatId) {
		return pinnedOf(chatId)
			.filter((p) => p.msg)
			.map((p) => messageInfo(p.msg));
	}

	async function replyPrivately(messageId, text) {
		const m = getMsg(messageId);
		if (!req("WAWebMsgReply").canPrivateReply(m)) {
			throw new Error("cannotReplyPrivately");
		}
		const wid = req("WAWebGroupAgentOneToOneContact").getGroupAgentAwareOneToOneContact(
			m.author,
			req("WAWebFrontendMsgGetters").getChat(m),
			"private_reply"
		);
		const found = await req("WAWebFindChatAction").findOrCreateLatestChat(wid, "privateReplyToMsg");
		await req("WAWebSendTextMsgChatAction").sendTextMsgToChat(found.chat, String(text), { quotedMsg: m });
		return chatInfo(found.chat);
	}

	// Who reacted with what, with names.
	async function reactionDetails(messageId) {
		const all = await collections().Reactions.find(getMsg(messageId).id);
		const me = myIdSet();
		const C = collections();
		return ((all && all.reactions && all.reactions.getModelsArray()) || []).map((r) => ({
			emoji: r.aggregateEmoji,
			people: r.senders.getModelsArray().map((s) => ({
				name:
					personName(s.senderObj || C.Contact.get(s.senderUserJid)) || String(s.senderUserJid).split("@")[0],
				isMe: me.has(String(s.senderUserJid)),
				t: Math.floor((s.timestamp || 0) / 1000),
			})),
		}));
	}

	async function sendContacts(chatId, contactIds) {
		await req("WAWebAttachVcardsFlowLoadable").requireBundle();
		req("WAWebSendContactsAction")({ chat: getChat(chatId), contacts: contactsOf(contactIds) });
		return true;
	}

	function stickerList() {
		const recent = req("WAWebRecentStickerCollectionMd").RecentStickerCollectionMd.map((r) => r.sticker);
		let favorite = [];
		try {
			favorite = req("WAWebFavoriteStickerCollection").FavoriteStickerCollection.map((r) => r.sticker);
		} catch (e) {}
		return { recent: recent.filter(Boolean), favorite: favorite.filter(Boolean) };
	}

	function stickers() {
		const list = stickerList();
		const describe = (s, i, kind) => ({
			index: i,
			kind: kind,
			label: (s.mediaData && s.mediaData.accessibilityLabel) || "",
			pack: s.stickerPackName || "",
			animated: !!(s.mediaData && s.mediaData.isAnimated),
		});
		return list.favorite.map((s, i) => describe(s, i, "favorite")).concat(list.recent.map((s, i) => describe(s, i, "recent")));
	}

	async function sendSticker(chatId, kind, index) {
		const sticker = stickerList()[kind][index];
		if (!sticker) {
			throw new Error("stickerNotFound");
		}
		try {
			await sticker.downloadMedia();
		} catch (e) {}
		await req("WAWebSendStickerAction").sendStickerToChat(getChat(chatId), sticker, {
			stickerSendOrigin: kind === "favorite" ? 4 : 3,
		});
		return true;
	}

	// WhatsApp's own search over every chat, from its index on this computer.
	async function searchAll(query, page) {
		const found = await req("WAWebMsgCollection").MsgCollection.search(String(query), page || 1, 40);
		return {
			done: !!found.eof,
			messages: (found.messages || []).map((m) => {
				const info = messageInfo(m);
				const chat = req("WAWebFrontendMsgGetters").getChat(m);
				info.chatTitle = chat ? chatTitle(chat) : "";
				return info;
			}),
		};
	}

	// A chat's photos and videos, links, or documents, newest first, as its info shows them.
	async function chatMedia(chatId, kind) {
		const chat = getChat(chatId);
		let list;
		if (kind === "links") {
			list = chat.getLinkMsgs();
			await list.queryLinks(chat);
		} else if (kind === "docs") {
			list = chat.getDocMsgs();
			await list.queryDocs(chat);
		} else {
			list = chat.getMediaMsgs();
			await list.queryMedia({ chat: chat });
		}
		return list
			.getModelsArray()
			.slice()
			.sort((a, b) => (b.t || 0) - (a.t || 0))
			.map(messageInfo);
	}

	// The messages that mention the user and are not read yet, oldest first, as WhatsApp's @ button.
	async function unreadMentions(chatId) {
		const chat = getChat(chatId);
		const md = chat.unreadMentionMetadata;
		if (!md || !md.unreadMentionCollection) {
			return [];
		}
		const ids = md.unreadMentionCollection
			.getModelsArray()
			.map((x) => x.id)
			.reverse();
		if (!ids.length) {
			return [];
		}
		const found = await collections().Msg.getMessagesById(ids);
		return ((found && found.messages) || []).map(messageInfo);
	}

	// Events ----------------------------------------------------------------------------------------------

	function eventInfo(messageId) {
		const m = getMsg(messageId);
		const key = req("WAWebReferentialMsgKey").getReferentialMsgKey(m);
		const T = req("WAWebProtobufsE2E.pb")["Message$EventResponseMessage$EventResponseType"];
		const groups = { going: [], maybe: [], notGoing: [] };
		let responses = [];
		try {
			responses = req("WAWebEventResponseCollection").EventResponseCollection.byParent(key).toArray();
		} catch (e) {}
		for (const r of responses) {
			const who = contactName(r.sender);
			if (r.eventResponse === T.GOING) {
				groups.going.push(who);
			} else if (r.eventResponse === T.MAYBE) {
				groups.maybe.push(who);
			} else if (r.eventResponse === T.NOT_GOING) {
				groups.notGoing.push(who);
			}
		}
		const location = m.eventLocation || {};
		return Object.assign(
			{
				name: m.eventName || "",
				description: m.eventDescription || "",
				start: m.eventStartTime || 0,
				end: m.eventEndTime || 0,
				location: location.name || location.address || "",
				link: m.eventJoinLink || "",
				canceled: !!m.isEventCanceled,
			},
			groups
		);
	}

	async function respondToEvent(messageId, answer) {
		const T = req("WAWebProtobufsE2E.pb")["Message$EventResponseMessage$EventResponseType"];
		const value = { going: T.GOING, maybe: T.MAYBE, notGoing: T.NOT_GOING }[answer];
		await req("WAWebSendEventResponseMsgAction").sendEventResponseMsg(
			value,
			req("WAWebFrontendMsgGetters").getAsEventCreation(getMsg(messageId))
		);
		return true;
	}

	async function createEvent(chatId, options) {
		await loadBundle("WAWebEventsCreateEventModalFlow.react");
		const opts = { name: String(options.name), startTime: Math.floor(Number(options.start)) };
		if (options.description) {
			opts.description = String(options.description);
		}
		if (options.end) {
			opts.endTime = Math.floor(Number(options.end));
		}
		if (options.location) {
			opts.location = String(options.location);
		}
		if (options.callType) {
			opts.callType = options.callType;
		}
		await req("WAWebSendEventCreationMsgAction").sendEventCreationMessage({ chat: getChat(chatId), eventCreationOpts: opts });
		return true;
	}

	// Your status, profile and privacy --------------------------------------------------------------------

	const STATUS_COLORS = [
		4289080433, 4287670337, 4290879551, 4286128440, 4289628020, 4293964592, 4290163495, 4291207116, 4287326608,
		4294937228, 4283744869, 4294933355, 4280730844, 4283943423, 4285818730, 4286484643, 4283864831, 4285408638,
		4286237605, 4280563264, 4286747850,
	];

	async function postTextStatus(text, colorIndex, font) {
		const color = STATUS_COLORS[Math.abs(Number(colorIndex) || 0) % STATUS_COLORS.length];
		const result = await req("WAWebSendStatusMsgAction").sendStatusTextMsgAction({
			text: String(text),
			color: color,
			font: Number(font) || 0,
		});
		if (result && result.messageSendResult && result.messageSendResult !== "OK") {
			throw new Error("sendFailed");
		}
		return true;
	}

	async function myStatuses() {
		const C = collections();
		const mine = C.Status.getMyStatus();
		if (!mine) {
			return [];
		}
		const result = [];
		for (const m of mine.msgs.getModelsArray().filter((x) => x.type !== "revoked" && !x.isNotification)) {
			let viewers = [];
			try {
				const info = await C.MsgInfo.find(m.id);
				const read = info && info.read && info.read.getModelsArray ? info.read.getModelsArray() : [];
				viewers = read.map((r) => ({ name: contactName(r.id), t: r.t || 0 }));
			} catch (e) {}
			const item = messageInfo(m);
			item.viewers = viewers;
			result.push(item);
		}
		return result.reverse();
	}

	async function deleteMyStatus(messageId) {
		await req("WAWebRevokeStatusAction").sendStatusRevokeMsgAction(collections().Status.getMyStatus(), getMsg(messageId));
		return true;
	}

	function meWid() {
		return req("WAWebUserPrefsMeUser").getMeUserOrThrow();
	}

	async function profile() {
		let about = "";
		try {
			const status = await req("WAWebStatusContactAction").getStatus(meWid());
			about = (status && status.status) || "";
		} catch (e) {}
		return { name: req("WAWebConnModel").Conn.pushname || "", about: about };
	}

	async function setProfile(field, value) {
		if (field === "name") {
			await loadBundle("WAWebProfileDrawer.react");
			await req("WAWebSetPushnameConnAction").setPushname(String(value));
		} else if (field === "about") {
			await req("WAWebStatusContactAction").setMyStatus(String(value));
		}
		return true;
	}

	// A square 640-pixel JPEG made from the uploaded picture, as WhatsApp's own cropper makes.
	async function setProfilePhoto(uploadId) {
		const thumb = req("WAWebProfilePicThumbCollection").ProfilePicThumbCollection.gadd(meWid());
		const action = req("WAWebProfilePicThumbAction");
		if (!uploadId) {
			await action.deleteProfilePic(thumb);
			return true;
		}
		const blob = new Blob(uploads.get(uploadId));
		uploads.delete(uploadId);
		const bitmap = await createImageBitmap(blob);
		const side = Math.min(bitmap.width, bitmap.height);
		const canvas = document.createElement("canvas");
		canvas.width = 640;
		canvas.height = 640;
		canvas.getContext("2d").drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, 640, 640);
		const full = canvas.toDataURL("image/jpeg", 0.9);
		await action.setProfilePic({ full: full, thumb: full, profilePicThumb: thumb });
		return true;
	}

	const PRIVACY_NAMES = {
		lastSeen: "last",
		online: "online",
		profilePicture: "profile",
		about: "status",
		readReceipts: "readreceipts",
		groupAdd: "groupadd",
		callAdd: "calladd",
		messages: "messages",
	};

	async function privacy() {
		let settings = null;
		try {
			settings = await req("WAWebQueryPrivacySettingsJob").getPrivacy();
		} catch (e) {
			settings = req("WAWebUserPrefsGeneral").getUserPrivacySettings();
		}
		const result = {};
		for (const key of Object.keys(PRIVACY_NAMES)) {
			result[key] = settings && settings[key] != null ? String(settings[key]) : "";
		}
		return result;
	}

	async function setPrivacy(key, value) {
		const name = PRIVACY_NAMES[key];
		if (!name) {
			throw new Error("badSetting");
		}
		await req("WAWebSetPrivacyForOneCategoryAction").setPrivacyForOneCategory({ name: name, value: String(value) });
		return true;
	}

	function blockedContacts() {
		return req("WAWebBlocklistCollection")
			.BlocklistCollection.getModelsArray()
			.map((b) => {
				let name = contactName(b.id);
				if (!name || /^[0-9]+$/.test(name)) {
					// People known only by their newer id: show their phone number instead.
					try {
						name = "+" + req("WAWebApiContact").getPhoneNumber(b.id).user;
					} catch (e) {}
				}
				return { id: b.id.toString(), name: name };
			});
	}

	async function unblock(contactId) {
		const C = collections();
		const contact = C.Contact.get(contactId) || C.Contact.gadd(req("WAWebWidFactory").createWid(contactId));
		await req("WAWebBlockContactAction").unblockContact(contact, "profile");
		return true;
	}

	// Group calls -------------------------------------------------------------------------------------------

	async function startGroupCall(chatId) {
		await req("WAWebVoipStartCall").startWAWebVoipGroupCallFromChat(getChat(chatId), false, 0, 0);
		return true;
	}

	function ongoingGroupCall(chatId) {
		try {
			if (ringingGroupCall(getChat(chatId))) {
				return true;
			}
			const ongoing = req("WAWebVoipOngoingCallCollection").WAWebVoipOngoingCallCollection.getByChat(getChat(chatId));
			return !!ongoing;
		} catch (e) {
			return false;
		}
	}

	// The group's call when it is ringing for the user: being invited again rings, and then it is answered,
	// not joined; WhatsApp's join does nothing for a call that rings.
	function ringingGroupCall(chat) {
		let call = null;
		try {
			call = req("WAWebCallCollection").activeCall;
		} catch (e) {
			return null;
		}
		if (!call || !call.isGroup || String(call.groupJid) !== String(chat.id)) {
			return null;
		}
		const state = typeof call.getState === "function" ? call.getState() : call.state;
		const S = req("WAWebVoipCallStateUtils");
		return S.isCallRinging(state) || S.isCallIncoming(state) ? call : null;
	}

	async function joinGroupCall(chatId) {
		const chat = getChat(chatId);
		if (ringingGroupCall(chat)) {
			return answerCall();
		}
		const ongoing = req("WAWebVoipOngoingCallCollection").WAWebVoipOngoingCallCollection.getByChat(chat);
		if (!ongoing) {
			throw new Error("noOngoingCall");
		}
		await req("WAWebVoipStartCall").joinOngoingWAWebVoipGroupCallPN({ callId: ongoing.id.id, chat: chat, isVideo: false });
		return true;
	}

	// Connection --------------------------------------------------------------------------------------------

	function connectionState() {
		const socket = req("WAWebSocketModel").Socket;
		const stream = req("WAWebStreamModel").Stream;
		let online = true;
		try {
			online = req("WAWebNetworkStatus").online !== false;
		} catch (e) {}
		return { info: String(stream.info || ""), mode: String(stream.mode || ""), socket: String(socket.state || ""), online: online };
	}

	async function chatAction(chatId, action, seconds) {
		const chat = getChat(chatId);
		if (action === "archive" || action === "unarchive") {
			await req("WAWebSetArchiveChatAction").setArchive(chat, action === "archive");
		} else if (action === "pin" || action === "unpin") {
			await req("WAWebSetPinChatAction").setPin(chat, action === "pin");
		} else if (action === "markUnread") {
			await req("WAWebUpdateUnreadChatAction").markUnread(chat, true);
		} else if (action === "markRead") {
			await markSeen(chatId);
		} else if (action === "mute") {
			// -1 mutes until the user unmutes; otherwise seconds from now.
			const expiration = seconds === -1 ? -1 : Math.floor(Date.now() / 1000) + seconds;
			await chat.mute.mute({ expiration: expiration, sendDevice: true });
		} else if (action === "unmute") {
			await chat.mute.unmute({ sendDevice: true });
		} else {
			throw new Error("unknownAction:" + action);
		}
		return true;
	}

	// Voice notes: recording -----------------------------------------------------------------------------

	const OPUS_RATES = new Set([8000, 12000, 16000, 24000, 48000]);
	let recording = null;
	let recorded = null;

	function makeCrcTable() {
		const table = new Uint32Array(256);
		for (let i = 0; i < 256; i++) {
			let r = i << 24;
			for (let j = 0; j < 8; j++) {
				r = r & 0x80000000 ? ((r << 1) ^ 0x04c11db7) >>> 0 : (r << 1) >>> 0;
			}
			table[i] = r >>> 0;
		}
		return table;
	}
	const CRC_TABLE = makeCrcTable();

	function oggCrc(bytes) {
		let c = 0;
		for (let i = 0; i < bytes.length; i++) {
			c = ((c << 8) ^ CRC_TABLE[((c >>> 24) ^ bytes[i]) & 255]) >>> 0;
		}
		return c;
	}

	// Wraps Opus packets in an Ogg container (RFC 7845), the format of WhatsApp voice notes.
	function oggOpus(packets, channels, inputRate, preSkip) {
		const serial = (Math.random() * 2 ** 32) >>> 0;
		const pages = [];
		let sequence = 0;
		function page(packetList, granule, flags) {
			const lacing = [];
			for (const p of packetList) {
				let n = p.length;
				while (n >= 255) {
					lacing.push(255);
					n -= 255;
				}
				lacing.push(n);
			}
			const bodySize = packetList.reduce((s, p) => s + p.length, 0);
			const out = new Uint8Array(27 + lacing.length + bodySize);
			const view = new DataView(out.buffer);
			out.set([0x4f, 0x67, 0x67, 0x53], 0);
			out[5] = flags;
			view.setBigUint64(6, BigInt(granule), true);
			view.setUint32(14, serial, true);
			view.setUint32(18, sequence++, true);
			out[26] = lacing.length;
			out.set(lacing, 27);
			let offset = 27 + lacing.length;
			for (const p of packetList) {
				out.set(p, offset);
				offset += p.length;
			}
			view.setUint32(22, oggCrc(out), true);
			pages.push(out);
		}
		const ascii = (s) => Array.from(s, (c) => c.charCodeAt(0));
		const head = new Uint8Array(19);
		const headView = new DataView(head.buffer);
		head.set(ascii("OpusHead"), 0);
		head[8] = 1;
		head[9] = channels;
		headView.setUint16(10, preSkip, true);
		headView.setUint32(12, inputRate, true);
		page([head], 0, 2);
		const vendor = new TextEncoder().encode("WhatsApp Access");
		const tags = new Uint8Array(16 + vendor.length);
		const tagsView = new DataView(tags.buffer);
		tags.set(ascii("OpusTags"), 0);
		tagsView.setUint32(8, vendor.length, true);
		tags.set(vendor, 12);
		page([tags], 0, 0);
		let granule = preSkip;
		const perPage = 50;
		for (let i = 0; i < packets.length; i += perPage) {
			const group = packets.slice(i, i + perPage);
			for (const p of group) {
				granule += p.samples;
			}
			page(
				group.map((p) => p.data),
				granule,
				i + perPage >= packets.length ? 4 : 0,
			);
		}
		return new Blob(pages, { type: "audio/ogg; codecs=opus" });
	}

	async function microphones() {
		const devices = await navigator.mediaDevices.enumerateDevices();
		return devices
			.filter((d) => d.kind === "audioinput" && d.deviceId !== "default" && d.deviceId !== "communications")
			.map((d) => ({ id: d.deviceId, label: d.label }));
	}

	async function startRecording(options) {
		if (recording) {
			throw new Error("alreadyRecording");
		}
		options = options || {};
		const raw = options.raw !== false;
		const audio = {
			echoCancellation: !raw,
			noiseSuppression: !raw,
			autoGainControl: !raw,
			channelCount: options.stereo ? 2 : 1,
			sampleRate: 48000,
		};
		if (options.deviceId) {
			audio.deviceId = { exact: options.deviceId };
		}
		let stream;
		ownMicrophoneRequest = true;
		try {
			stream = await navigator.mediaDevices.getUserMedia({ audio: audio });
		} catch (e) {
			throw new Error("microphone:" + (e && e.name));
		} finally {
			ownMicrophoneRequest = false;
		}
		const track = stream.getAudioTracks()[0];
		const state = {
			stream: stream,
			track: track,
			packets: [],
			levels: [],
			encoder: null,
			channels: 0,
			sampleRate: 0,
			preSkip: 312,
			error: null,
			paused: false,
			started: performance.now(),
			label: track.label,
		};
		const bitrate = Math.min(256000, Math.max(16000, (options.kbps || 128) * 1000));
		const reader = new MediaStreamTrackProcessor({ track: track }).readable.getReader();
		state.done = (async () => {
			try {
				for (;;) {
					const { value: frame, done } = await reader.read();
					if (done) {
						break;
					}
					try {
						if (state.paused) {
							continue;
						}
						if (!state.encoder) {
							state.channels = Math.min(2, frame.numberOfChannels);
							state.sampleRate = frame.sampleRate;
							if (!OPUS_RATES.has(state.sampleRate)) {
								throw new Error("sampleRate:" + state.sampleRate);
							}
							state.encoder = new AudioEncoder({
								output: (chunk, meta) => {
									const data = new Uint8Array(chunk.byteLength);
									chunk.copyTo(data);
									state.packets.push({
										data: data,
										samples: Math.round(((chunk.duration || 20000) * 48000) / 1e6),
									});
									const description = meta && meta.decoderConfig && meta.decoderConfig.description;
									if (description && description.byteLength >= 12) {
										state.preSkip = new DataView(
											description.buffer || description,
											description.byteOffset || 0,
										).getUint16(10, true);
									}
								},
								error: (e) => {
									state.error = e;
								},
							});
							state.encoder.configure({
								codec: "opus",
								sampleRate: state.sampleRate,
								numberOfChannels: state.channels,
								bitrate: bitrate,
							});
						}
						const samples = new Float32Array(frame.numberOfFrames);
						frame.copyTo(samples, { planeIndex: 0, format: "f32-planar" });
						let sum = 0;
						for (let i = 0; i < samples.length; i++) {
							sum += samples[i] * samples[i];
						}
						state.levels.push(Math.sqrt(sum / Math.max(1, samples.length)));
						if (frame.numberOfChannels === state.channels) {
							state.encoder.encode(frame);
						} else {
							state.encoder.encode(copyChannels(frame, state.channels));
						}
					} finally {
						frame.close();
					}
				}
			} catch (e) {
				state.error = e;
			}
		})();
		recording = state;
		recorded = null;
		return { microphone: state.label };
	}

	function copyChannels(frame, channels) {
		const n = frame.numberOfFrames;
		const data = new Float32Array(n * channels);
		for (let c = 0; c < channels; c++) {
			const plane = new Float32Array(n);
			frame.copyTo(plane, { planeIndex: Math.min(c, frame.numberOfChannels - 1), format: "f32-planar" });
			data.set(plane, c * n);
		}
		return new AudioData({
			format: "f32-planar",
			sampleRate: frame.sampleRate,
			numberOfFrames: n,
			numberOfChannels: channels,
			timestamp: frame.timestamp,
			data: data,
		});
	}

	// WhatsApp shows voice notes with 64 bars from 0 to 100.
	function waveform(levels) {
		const bars = new Uint8Array(64);
		if (!levels.length) {
			return bars;
		}
		const per = levels.length / 64;
		let peak = 0;
		const values = [];
		for (let i = 0; i < 64; i++) {
			const slice = levels.slice(Math.floor(i * per), Math.max(Math.floor(i * per) + 1, Math.floor((i + 1) * per)));
			const value = slice.reduce((s, x) => s + x, 0) / Math.max(1, slice.length);
			values.push(value);
			peak = Math.max(peak, value);
		}
		for (let i = 0; i < 64; i++) {
			bars[i] = peak > 0 ? Math.round((values[i] / peak) * 100) : 0;
		}
		return bars;
	}

	async function finishRecording(state) {
		state.track.stop();
		state.stream.getTracks().forEach((t) => t.stop());
		await state.done;
		if (state.encoder && state.encoder.state === "configured") {
			await state.encoder.flush();
			state.encoder.close();
		}
		if (state.error) {
			throw new Error("recording:" + state.error);
		}
	}

	async function stopRecording() {
		const state = recording;
		if (!state) {
			throw new Error("notRecording");
		}
		recording = null;
		await finishRecording(state);
		if (!state.packets.length) {
			throw new Error("emptyRecording");
		}
		const blob = oggOpus(state.packets, state.channels, state.sampleRate, state.preSkip);
		const samples = state.packets.reduce((s, p) => s + p.samples, 0);
		const duration = samples / 48000;
		recorded = {
			file: new File([blob], "voice-note.ogg", { type: "audio/ogg; codecs=opus" }),
			waveform: waveform(state.levels),
			duration: duration,
			channels: state.channels,
		};
		return {
			duration: duration,
			channels: state.channels,
			sampleRate: state.sampleRate,
			bytes: blob.size,
		};
	}

	function pauseRecording() {
		if (!recording) {
			throw new Error("notRecording");
		}
		recording.paused = !recording.paused;
		return recording.paused;
	}

	async function cancelRecording() {
		const state = recording;
		recording = null;
		recorded = null;
		if (state) {
			try {
				await finishRecording(state);
			} catch (e) {
				// Nothing is kept, so a failure here does not matter.
			}
		}
		return true;
	}

	async function sendRecording(chatId) {
		if (!recorded) {
			throw new Error("noRecording");
		}
		const chat = chatOrStatus(chatId);
		const note = recorded;
		const data = await req("WAWebMediaOpaqueData").createFromData(note.file, note.file.type);
		const prep = req("WAWebPrepRawMedia").prepRawMedia(data, { isPtt: true });
		const mediaData = await prep.waitForPrep();
		try {
			if (typeof mediaData.set === "function") {
				mediaData.set({ waveform: note.waveform });
			} else {
				mediaData.waveform = note.waveform;
			}
		} catch (e) {
			// WhatsApp still sends the voice note without its bars.
		}
		const result = await prep.sendToChat({ chat: chat, options: {} });
		const status = result && result.messageSendResult;
		if (status && status !== "OK") {
			throw new Error("sendFailed:" + status);
		}
		recorded = null;
		return true;
	}

	// Files ----------------------------------------------------------------------------------------------

	// The add-on sends a file in base64 pieces, then asks for it to be sent.
	const uploads = new Map();

	function uploadStart(uploadId) {
		uploads.set(uploadId, []);
		return true;
	}

	function uploadChunk(uploadId, base64) {
		const parts = uploads.get(uploadId);
		if (!parts) {
			throw new Error("noUpload");
		}
		parts.push(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)));
		return parts.length;
	}

	function uploadCancel(uploadId) {
		uploads.delete(uploadId);
		return true;
	}

	// kind is photo, video, audio or document, as the add-on decided from the file's name.
	async function sendFile(chatId, uploadId, name, mime, kind, caption, quotedId) {
		const parts = uploads.get(uploadId);
		uploads.delete(uploadId);
		if (!parts) {
			throw new Error("noUpload");
		}
		const chat = chatOrStatus(chatId);
		const file = new File(parts, name, { type: mime || "application/octet-stream" });
		const prepOptions = kind === "document" ? { asDocument: true } : kind === "audio" ? { isAudio: true } : {};
		const data = await req("WAWebMediaOpaqueData").createFromData(file, file.type);
		const prep = req("WAWebPrepRawMedia").prepRawMedia(data, prepOptions);
		await prep.waitForPrep();
		const options = {};
		if (caption && kind !== "audio") {
			options.caption = caption;
		}
		if (quotedId) {
			options.quotedMsg = getMsg(quotedId);
		}
		const result = await prep.sendToChat({ chat: chat, options: options });
		const status = result && result.messageSendResult;
		if (status && status !== "OK") {
			throw new Error("sendFailed:" + status);
		}
		return true;
	}

	// Listening ------------------------------------------------------------------------------------------

	let player = null;
	let playerUrl = null;
	let playbackRate = 1;

	// 1, 1.5 or 2 times, as in WhatsApp. The pitch stays the same.
	function setPlaybackRate(rate) {
		playbackRate = Math.min(3, Math.max(0.5, Number(rate) || 1));
		if (player) {
			player.playbackRate = playbackRate;
		}
		return playbackRate;
	}

	// From 0 to 1, from the add-on's settings: one for chats, one for statuses.
	let playbackVolume = 1;

	function setPlaybackVolume(volume) {
		playbackVolume = Math.min(1, Math.max(0, Number(volume)));
		if (player) {
			player.volume = playbackVolume;
		}
		return playbackVolume;
	}

	function stopAudio() {
		const wasPlaying = !!(player && !player.paused);
		if (player) {
			player.pause();
			player = null;
		}
		if (playerUrl) {
			URL.revokeObjectURL(playerUrl);
			playerUrl = null;
		}
		return wasPlaying;
	}

	async function play(blob, messageId) {
		stopAudio();
		playerUrl = URL.createObjectURL(blob);
		player = new Audio(playerUrl);
		player.preservesPitch = true;
		player.playbackRate = playbackRate;
		player.volume = playbackVolume;
		// Voice notes and statuses play on the speaker chosen for calls too.
		const sink = callAudio.speaker ? await deviceIdFor("audiooutput", callAudio.speaker) : null;
		if (sink && player.setSinkId) {
			await player.setSinkId(sink).catch(() => {});
		}
		player.onended = () => emit({ type: "playbackEnded", messageId: messageId || null });
		await player.play();
		return true;
	}

	// The HKDF "info" WhatsApp uses to derive each kind of media's keys.
	const MEDIA_KEY_INFO = {
		ptt: "WhatsApp Audio Keys",
		audio: "WhatsApp Audio Keys",
		image: "WhatsApp Image Keys",
		sticker: "WhatsApp Image Keys",
		video: "WhatsApp Video Keys",
		ptv: "WhatsApp Video Keys",
		gif: "WhatsApp Video Keys",
		document: "WhatsApp Document Keys",
	};

	async function downloadMedia(m) {
		const info = MEDIA_KEY_INFO[m.type];
		if (!info || !m.directPath || !m.mediaKey) {
			throw new Error("noMedia");
		}
		const response = await fetch("https://mmg.whatsapp.net" + m.directPath);
		if (!response.ok) {
			throw new Error("mediaGone:" + response.status);
		}
		const encrypted = new Uint8Array(await response.arrayBuffer());
		const keyBytes = Uint8Array.from(atob(m.mediaKey), (c) => c.charCodeAt(0));
		const base = await crypto.subtle.importKey("raw", keyBytes, "HKDF", false, ["deriveBits"]);
		const expanded = new Uint8Array(
			await crypto.subtle.deriveBits(
				{ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: new TextEncoder().encode(info) },
				base,
				112 * 8,
			),
		);
		const key = await crypto.subtle.importKey("raw", expanded.slice(16, 48), "AES-CBC", false, ["decrypt"]);
		const plain = await crypto.subtle.decrypt(
			{ name: "AES-CBC", iv: expanded.slice(0, 16) },
			key,
			encrypted.slice(0, -10),
		);
		return new Blob([plain], { type: (m.mimetype || "audio/ogg").split(";")[0] });
	}

	// Downloads a message's file for the add-on to save, which then reads it in base64 pieces.
	const downloads = new Map();

	const EXTENSIONS = {
		"image/jpeg": ".jpg",
		"image/png": ".png",
		"image/webp": ".webp",
		"image/gif": ".gif",
		"video/mp4": ".mp4",
		"video/3gpp": ".3gp",
		"audio/ogg": ".ogg",
		"audio/mpeg": ".mp3",
		"audio/mp4": ".m4a",
		"audio/aac": ".aac",
		"application/pdf": ".pdf",
	};

	function suggestedName(m, mime) {
		if (m.filename) {
			return m.filename;
		}
		const when = new Date((m.t || 0) * 1000);
		const pad = (n) => String(n).padStart(2, "0");
		const stamp =
			when.getFullYear() + "-" + pad(when.getMonth() + 1) + "-" + pad(when.getDate()) +
			" at " + pad(when.getHours()) + "." + pad(when.getMinutes()) + "." + pad(when.getSeconds());
		const kinds = { image: "Image", sticker: "Sticker", video: "Video", ptv: "Video", ptt: "Audio", audio: "Audio" };
		return "WhatsApp " + (kinds[m.type] || "File") + " " + stamp + (EXTENSIONS[mime] || "");
	}

	function suggestedFileName(messageId) {
		const m = getMsg(messageId);
		return suggestedName(m, (m.mimetype || "").split(";")[0]);
	}

	async function downloadStart(messageId) {
		const m = getMsg(messageId);
		const blob = await downloadMedia(m);
		const bytes = new Uint8Array(await blob.arrayBuffer());
		const id = messageId + ":" + Date.now();
		downloads.set(id, bytes);
		return { id: id, size: bytes.length, name: suggestedName(m, blob.type), mime: blob.type };
	}

	function downloadChunk(id, offset, length) {
		const bytes = downloads.get(id);
		if (!bytes) {
			throw new Error("noDownload");
		}
		const part = bytes.subarray(offset, offset + length);
		let text = "";
		for (let i = 0; i < part.length; i += 32768) {
			text += String.fromCharCode.apply(null, part.subarray(i, i + 32768));
		}
		return btoa(text);
	}

	function downloadEnd(id) {
		downloads.delete(id);
		return true;
	}

	async function playMessage(messageId) {
		// getMsg also finds statuses, which are not in the chats' messages.
		const m = getMsg(messageId);
		return play(await downloadMedia(m), messageId);
	}

	async function playRecording() {
		if (!recorded) {
			throw new Error("noRecording");
		}
		return play(recorded.file, null);
	}

	// Contact and group info, as WhatsApp shows it ---------------------------------------------------

	async function contactInfo(chatId) {
		const chat = getChat(chatId);
		const C = collections();
		if (isGroupChat(chat)) {
			const gm = chat.groupMetadata || {};
			const people = gm.participants ? gm.participants.getModelsArray() : [];
			const myIds = myIdSet();
			const owner = gm.owner ? personName(C.Contact.get(gm.owner)) || String(gm.owner.user || gm.owner) : "";
			return {
				kind: "group",
				title: chatTitle(chat),
				description: gm.desc || "",
				created: gm.creation || 0,
				creator: owner,
				participants: people
					.map((p) => ({
						name: personName(C.Contact.get(p.id)) || String(p.id.user),
						admin: !!(p.isAdmin || p.isSuperAdmin),
						isMe: myIds.has(p.id.toString()),
					}))
					.sort((a, b) => b.isMe - a.isMe || b.admin - a.admin || a.name.localeCompare(b.name)),
			};
		}
		const contact = C.Contact.get(chat.id) || {};
		let about = "";
		try {
			const status = await req("WAWebStatusContactAction").getStatus(chat.id);
			about = ((status && (status.status || (status.attributes && status.attributes.status))) || "").trim();
		} catch (e) {
			// About is not shared with everyone.
		}
		let common = [];
		try {
			common = (await req("WAWebFindCommonGroupsContactAction").findCommonGroups(contact)).map((g) => {
				const groupChat = C.Chat.get(g.id);
				return groupChat ? chatTitle(groupChat) : String(g.id);
			});
		} catch (e) {
			// Leave the list empty.
		}
		const phone = contact.phoneNumber || (chat.id.server === "c.us" ? chat.id : null);
		return {
			kind: "user",
			title: chatTitle(chat),
			name: contact.name || "",
			pushname: contact.pushname || "",
			phone: phone && phone.user ? "+" + phone.user : "",
			about: about || contact.textStatusString || "",
			business: !!contact.isBusiness,
			blocked: !!contact.isContactBlocked,
			commonGroups: common,
		};
	}

	// Status updates ---------------------------------------------------------------------------------------

	// The people who posted statuses, unseen first, each with their status items oldest first.
	function statuses() {
		const C = collections();
		if (!C.Status) {
			return [];
		}
		const myIds = myIdSet();
		return C.Status.getModelsArray()
			.filter((s) => s.msgs && s.msgs.length && !myIds.has(String(s.id)))
			.map((s) => {
				const items = s.msgs
					.getModelsArray()
					.filter((m) => !m.isNotification && m.type !== "revoked")
					.map((m) => {
						const info = messageInfo(m);
						info.viewed = (typeof m.ack === "number" && m.ack >= 3) || !!m.isViewed;
						return info;
					});
				const last = items.length ? items[items.length - 1] : null;
				return {
					id: String(s.id),
					name: personName(C.Contact.get(s.id)) || String((s.id && s.id.user) || s.id),
					unread: Math.max(0, s.unreadCount || 0),
					t: last ? last.t : s.t || 0,
					items: items,
				};
			})
			.filter((s) => s.items.length)
			.sort((a, b) => (b.unread > 0) - (a.unread > 0) || b.t - a.t);
	}

	// Seen, as viewing it in WhatsApp does: the poster sees the user among the viewers, unless the user
	// turned read receipts off in WhatsApp.
	async function statusSeen(messageId) {
		const m = getMsg(messageId);
		return !!(await req("WAWebContactStatusBridge").sendReadStatus(m, undefined, undefined));
	}

	async function likeStatus(messageId, emoji) {
		await req("WAWebSendReactionMsgAction").sendReactionToMsg(getMsg(messageId), emoji || "\u2764\ufe0f");
		return true;
	}

	// A reply to a status goes to the poster's chat, quoting the status, as in WhatsApp.
	async function replyStatus(messageId, text) {
		if (typeof text !== "string" || !text.trim()) {
			throw new Error("emptyMessage");
		}
		const m = getMsg(messageId);
		const author = m.author || (m.id && m.id.participant) || m.from;
		const result = await req("WAWebFindChatAction").findOrCreateLatestChat(author);
		const chat = (result && result.chat) || result;
		await req("WAWebSendTextMsgChatAction").sendTextMsgToChat(chat, text, { quotedMsg: m });
		return true;
	}

	// Recent calls, newest first, from the call entries WhatsApp keeps in chats.
	// The group calls going on now that the user could join, as WhatsApp's Join buttons show them.
	function ongoingCalls() {
		const C = collections();
		let list = [];
		try {
			list = req("WAWebVoipOngoingCallCollection").WAWebVoipOngoingCallCollection.getModelsArray();
		} catch (e) {
			return [];
		}
		let active = null;
		try {
			active = req("WAWebCallCollection").activeCall;
		} catch (e) {}
		const result = [];
		for (const m of list) {
			const chat = m.id && m.id.remote && C.Chat.get(m.id.remote);
			if (!chat) {
				continue;
			}
			const joined = !!(active && active.isGroup && String(active.groupJid) === String(chat.id) && !ringingGroupCall(chat));
			result.push({
				id: "ongoing_" + msgId(m),
				chatId: String(chat.id),
				name: chatTitle(chat),
				group: true,
				ongoing: true,
				joined: joined,
				video: !!m.isVideoCall,
				t: m.t || 0,
			});
		}
		return result;
	}

	function recentCalls(limit) {
		const C = collections();
		return ongoingCalls().concat(recentCallLog(C, limit));
	}

	function recentCallLog(C, limit) {
		return C.Msg.getModelsArray()
			.filter((m) => m.type === "call_log")
			.sort((a, b) => (b.t || 0) - (a.t || 0))
			.slice(0, limit || 100)
			.map((m) => {
				const chat = m.id.remote && C.Chat.get(m.id.remote);
				const duration = Number(m.callDuration) || 0;
				return {
					id: msgId(m),
					chatId: chat ? chat.id._serialized : String(m.id.remote),
					name: chat ? chatTitle(chat) : String((m.id.remote && m.id.remote.user) || ""),
					outgoing: !!m.id.fromMe,
					missed: !m.id.fromMe && !duration,
					video: !!m.isVideoCall,
					group: !!(chat && isGroupChat(chat)),
					duration: duration,
					t: m.t || 0,
				};
			});
	}

	// Calls ----------------------------------------------------------------------------------------------

	// The microphone and sound processing WhatsApp gets when it asks for the microphone for a call.
	// The add-on's own voice note recording asks separately and is left alone.
	let callAudio = { microphone: "", processing: "whatsapp", speaker: "" };
	let ownMicrophoneRequest = false;
	let originalGetUserMedia = null;
	// The speaker WhatsApp was last told to use; null until it is told once.
	let appliedSpeaker = null;

	// A device's id from its name; "default" (the browser's, which follows Windows) for an empty name.
	async function deviceIdFor(kind, label) {
		if (!label) {
			return "default";
		}
		const devices = await navigator.mediaDevices.enumerateDevices();
		const device = devices.find((d) => d.kind === kind && d.label === label);
		return device ? device.deviceId : null;
	}

	// The microphones and speakers, by name, without the browser's "Default" and "Communications" copies.
	async function audioDevices() {
		const devices = await navigator.mediaDevices.enumerateDevices();
		const named = (kind) =>
			devices
				.filter((d) => d.kind === kind && d.deviceId !== "default" && d.deviceId !== "communications")
				.map((d) => d.label);
		return { microphones: named("audioinput"), speakers: named("audiooutput") };
	}

	function callInProgress() {
		try {
			return !!req("WAWebCallCollection").activeCall;
		} catch (e) {
			return false;
		}
	}

	// Changes take effect at once: during a call through WhatsApp's own device switching, as when the
	// user picks another device in WhatsApp's call screen; otherwise for the next call.
	async function setCallAudio(options) {
		options = options || {};
		const before = callAudio;
		callAudio = {
			microphone: options.microphone || "",
			processing: options.processing || "whatsapp",
			speaker: options.speaker || "",
		};
		if (options.volume !== undefined) {
			setCallVolume(options.volume);
		}
		const result = { speaker: false, microphone: false };
		const devices = req("WAWebVoipAudioCaptureAndPlayback");
		if (callAudio.speaker !== appliedSpeaker) {
			const id = await deviceIdFor("audiooutput", callAudio.speaker);
			if (id) {
				try {
					// With no call, WhatsApp keeps it as its choice for the next one.
					await devices.switchAudioOutputDevice(id);
					appliedSpeaker = callAudio.speaker;
					result.speaker = true;
				} catch (e) {
					// The browser's speaker stays.
				}
				if (player && player.setSinkId) {
					player.setSinkId(id).catch(() => {});
				}
			}
		}
		if (callAudio.microphone !== before.microphone && callInProgress()) {
			const id = await deviceIdFor("audioinput", callAudio.microphone);
			if (id) {
				try {
					result.microphone = !!(await devices.switchAudioInputDevice(id));
				} catch (e) {
					// The call keeps its microphone.
				}
			}
		}
		return result;
	}

	// How loud the other person is in a call, from 0 to 1. WhatsApp plays call audio either through an
	// AudioContext or a media element showing a stream; both are caught as they are made, so a change
	// applies at once, during the call too.
	let callVolume = 1;
	const callGains = new Set();
	const callMedia = new Set();

	function installCallVolume() {
		if (window.__waAccessCallVolume) {
			return;
		}
		window.__waAccessCallVolume = true;
		const connect = AudioNode.prototype.connect;
		AudioNode.prototype.connect = function (target, ...rest) {
			if (target instanceof AudioDestinationNode && !this.__waAccessGain) {
				const context = target.context;
				if (!context.__waAccessGain) {
					const gain = context.createGain();
					gain.__waAccessGain = true;
					gain.gain.value = callVolume;
					connect.call(gain, target);
					context.__waAccessGain = gain;
					callGains.add(gain);
				}
				connect.call(this, context.__waAccessGain, ...rest);
				return target;
			}
			return connect.call(this, target, ...rest);
		};
		const source = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, "srcObject");
		Object.defineProperty(HTMLMediaElement.prototype, "srcObject", {
			configurable: true,
			enumerable: source.enumerable,
			get() {
				return source.get.call(this);
			},
			set(value) {
				source.set.call(this, value);
				if (value instanceof MediaStream) {
					callMedia.add(this);
					this.volume = callVolume;
				} else {
					callMedia.delete(this);
				}
			},
		});
	}

	function setCallVolume(volume) {
		installCallVolume();
		callVolume = Math.min(1, Math.max(0, Number(volume)));
		for (const gain of callGains) {
			gain.gain.value = callVolume;
		}
		for (const media of callMedia) {
			media.volume = callVolume;
		}
		return callVolume;
	}

	async function callAudioConstraints(audio) {
		const result = typeof audio === "object" && audio ? Object.assign({}, audio) : {};
		if (callAudio.microphone) {
			try {
				const devices = await navigator.mediaDevices.enumerateDevices();
				const device = devices.find((d) => d.kind === "audioinput" && d.label === callAudio.microphone);
				if (device) {
					result.deviceId = { exact: device.deviceId };
				}
			} catch (e) {
				// The browser's default microphone, then.
			}
		}
		if (callAudio.processing === "echoOnly") {
			result.echoCancellation = true;
			result.noiseSuppression = false;
			result.autoGainControl = false;
		} else if (callAudio.processing === "none") {
			result.echoCancellation = false;
			result.noiseSuppression = false;
			result.autoGainControl = false;
		}
		return result;
	}

	function hookMicrophone() {
		if (originalGetUserMedia || !navigator.mediaDevices) {
			return;
		}
		originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
		navigator.mediaDevices.getUserMedia = async function (constraints) {
			if (!ownMicrophoneRequest && constraints && constraints.audio) {
				constraints = Object.assign({}, constraints, { audio: await callAudioConstraints(constraints.audio) });
			}
			return originalGetUserMedia(constraints);
		};
	}

	function unhookMicrophone() {
		if (originalGetUserMedia) {
			navigator.mediaDevices.getUserMedia = originalGetUserMedia;
			originalGetUserMedia = null;
		}
	}

	function voipStack() {
		return req("WAWebVoipStackInterface").getVoipStackInterface();
	}

	// The call in progress, ringing, or just ended; null when there is none.
	function callState() {
		let call;
		try {
			call = req("WAWebCallCollection").activeCall;
		} catch (e) {
			return null;
		}
		if (!call) {
			return null;
		}
		const S = req("WAWebVoipCallStateUtils");
		const state = typeof call.getState === "function" ? call.getState() : call.state;
		const peer = call.peerJid;
		const C = collections();
		let name = null;
		try {
			// A group call is named after its group, as WhatsApp shows it.
			const group = call.isGroup && call.groupJid ? C.Chat.get(call.groupJid) : null;
			name = group ? chatTitle(group) : personName(C.Contact.get(peer));
			if (!name) {
				const chat = C.Chat.get(peer);
				name = chat ? chatTitle(chat) : null;
			}
		} catch (e) {
			// The number below.
		}
		const check = (f) => {
			try {
				return !!S[f](state);
			} catch (e) {
				return false;
			}
		};
		return {
			id: String(call.id),
			state: String(state),
			incoming: !call.outgoing,
			ringing: check("isCallRinging") || check("isCallIncoming"),
			connecting: check("isCallConnecting"),
			connected: check("isCallConnected"),
			ended: check("isCallTerminal"),
			video: !!call.isVideo,
			group: !!call.isGroup,
			name: name || (peer && peer.user ? "+" + peer.user : ""),
			chatId: peer ? String(peer) : "",
			since: call.offerTime || 0,
			muted: !!call.selfMicMuted,
			participants: call.isGroup ? callParticipants(call) : [],
			myHand: call.isGroup ? callFlag(call, "isHandRaisedForParticipant", meWid()) : false,
		};
	}

	// Who spoke when, in the group call: WhatsApp tells the call each time someone's voice is heard.
	const lastSpoke = new Map();
	let speakerCall = null;

	function noteSpeaker(data) {
		if (data && data.participantJid) {
			lastSpoke.set(String(data.participantJid), Date.now());
		}
	}

	function watchSpeakers(call) {
		if (speakerCall === call) {
			return;
		}
		if (speakerCall && speakerCall.off) {
			speakerCall.off("participantAudioLevelChange", noteSpeaker);
		}
		speakerCall = call;
		lastSpoke.clear();
		if (call && call.on) {
			call.on("participantAudioLevelChange", noteSpeaker);
		}
	}

	const SPEAKING_MS = 2500;

	// The people heard in the last moments, the most recent first.
	function speakers() {
		let call;
		try {
			call = req("WAWebCallCollection").activeCall;
		} catch (e) {
			return [];
		}
		if (!call) {
			return [];
		}
		if (!call.isGroup) {
			return call.peerAudioLevel > 0 ? [callState().name] : [];
		}
		const now = Date.now();
		const mine = myIdSet();
		return [...lastSpoke]
			.filter(([jid, at]) => now - at < SPEAKING_MS && !mine.has(jid))
			.sort((a, b) => b[1] - a[1])
			.map(([jid]) => contactName(jid));
	}

	function callFlag(call, method, jid) {
		try {
			return !!call[method](jid);
		} catch (e) {
			return false;
		}
	}

	// Everyone invited to a group call: whether they are in it, muted, or have a hand raised.
	function callParticipants(call) {
		watchSpeakers(call);
		const connected = new Set((call.groupCallParticipantsConnected || []).map(String));
		const mine = myIdSet();
		const people = [];
		for (const jid of call.groupCallParticipants || []) {
			const id = String(jid);
			if (mine.has(id)) {
				continue;
			}
			people.push({
				id: id,
				name: contactName(jid),
				connected: connected.has(id),
				muted: callFlag(call, "isParticipantMicMuted", jid),
				hand: callFlag(call, "isHandRaisedForParticipant", jid),
				reaction: callReactionOf(call, jid),
			});
		}
		return people;
	}

	// The emoji someone just sent in the call; WhatsApp shows it for a few seconds, then clears it.
	function callReactionOf(call, jid) {
		try {
			const value = call.getReactionForParticipant(jid);
			if (!value) {
				return "";
			}
			return String(typeof value === "string" ? value : value.reaction || value.emoji || value.reactionText || "");
		} catch (e) {
			return "";
		}
	}

	async function raiseHand(raised) {
		const stack = await voipStack();
		await stack.raiseHand(!!raised);
		return !!raised;
	}

	async function callReaction(emoji) {
		const stack = await voipStack();
		await stack.sendReaction(String(emoji || ""));
		return true;
	}

	// Asks someone in the group call to mute their microphone, as WhatsApp's participant menu does.
	async function askToMute(jid) {
		const stack = await voipStack();
		await stack.requestPeerMute(req("WAWebWidFactory").createWid(jid));
		return true;
	}

	// Answers with the microphone on and the camera off, as a voice call even when it is a video call.
	async function answerCall() {
		const stack = await voipStack();
		try {
			req("WAWebCallRingtone").stopCallRingtone();
		} catch (e) {
			// No ringtone playing.
		}
		try {
			req("WAWebVoipCallAudioUnlock").prepareCallAudioElement();
		} catch (e) {
			// Older versions play call audio without this.
		}
		await stack.acceptCall(true, false, 0);
		return true;
	}

	async function declineCall() {
		const stack = await voipStack();
		await stack.rejectCallWithEndReason(req("WAWebVoipWaCallEnums").RejectEndReason.Self);
		return true;
	}

	async function endCall() {
		const stack = await voipStack();
		await stack.endCall(req("WAWebVoipSignalingEnums").EndCallReason.Self, true);
		return true;
	}

	async function muteCall(muted) {
		const stack = await voipStack();
		await stack.setCallMute(!!muted);
		return !!muted;
	}

	// Calls a person, as WhatsApp's call button does.
	async function startCall(chatId, video) {
		const chat = getChat(chatId);
		if (isGroupChat(chat)) {
			throw new Error("groupCall");
		}
		const started = await req("WAWebVoipStartCall").startWAWebVoipCall(chat.id, !!video, 0, 0, null, {
			entryTrust: "user_gesture",
		});
		if (started === false) {
			throw new Error("callNotStarted");
		}
		return true;
	}

	// Who is online, typing or recording --------------------------------------------------------------

	// A person's name, as WhatsApp shows it. People known only by their newer id (lid) are found by
	// their phone number: the contact saved under it, or else the number itself.
	function contactName(wid) {
		try {
			const C = collections();
			const name = personName(C.Contact.get(wid));
			if (name) {
				return name;
			}
			const id = typeof wid === "string" ? req("WAWebWidFactory").createWid(wid) : wid;
			if (id.server === "lid") {
				try {
					const phone = req("WAWebApiContact").getPhoneNumber(id);
					if (phone) {
						return personName(C.Contact.get(phone)) || "+" + phone.user;
					}
				} catch (e) {}
			}
			return String(id.user || id);
		} catch (e) {
			return String(wid);
		}
	}

	function presenceOf(chat) {
		const pres = chat.presence;
		if (!pres) {
			return { kind: isGroupChat(chat) ? "group" : "user", state: "unknown" };
		}
		if (isGroupChat(chat)) {
			return {
				kind: "group",
				typing: (pres.typingUserIds || []).map(contactName),
				recording: (pres.recordingUserIds || []).map(contactName),
			};
		}
		const cs = pres.chatstate || {};
		const states = { available: "online", typing: "typing", recording_audio: "recording", unavailable: "offline" };
		return {
			kind: "user",
			state: pres.hasData ? states[cs.type] || "offline" : "unknown",
			lastSeen: typeof cs.t === "number" && cs.t > 0 ? cs.t : null,
		};
	}

	let watched = null;

	// Others' online state and last seen reach only someone who is online. WhatsApp Web is online while it
	// is in front; the add-on is online while its window is open.
	function setOnline(on) {
		const action = req("WAWebPresenceChatAction");
		if (on) {
			action.sendPresenceAvailable();
			// Back in front: ask again for the open chat's state, which was not sent while offline.
			if (watched) {
				try {
					const chat = getChat(watched.chatId);
					const bridge = req("WAWebContactPresenceBridge");
					if (isGroupChat(chat)) {
						bridge.subscribeGroupPresence(chat.id);
					} else {
						bridge.subscribeUserPresence(chat.id);
					}
				} catch (e) {}
			}
		} else {
			action.sendPresenceUnavailable();
		}
		return true;
	}

	async function presence(chatId) {
		const chat = getChat(chatId);
		if (chat.presence && !chat.presence.isSubscribed) {
			try {
				setOnline(true);
				const bridge = req("WAWebContactPresenceBridge");
				if (isGroupChat(chat)) {
					bridge.subscribeGroupPresence(chat.id);
				} else {
					await bridge.subscribeUserPresence(chat.id);
				}
				// The answer comes a moment later; the watcher below reports it when it does.
			} catch (e) {
				// Without a subscription WhatsApp may still know something.
			}
		}
		return presenceOf(chat);
	}

	// Watches one chat's presence while it is open in the add-on, and reports changes.
	async function watchPresence(chatId) {
		if (watched) {
			clearInterval(watched.timer);
			watched = null;
		}
		if (!chatId) {
			return null;
		}
		const first = await presence(chatId);
		const state = { chatId: chatId, last: JSON.stringify(first) };
		state.timer = setInterval(() => {
			let now;
			try {
				now = presenceOf(getChat(chatId));
			} catch (e) {
				return;
			}
			const text = JSON.stringify(now);
			if (text !== state.last) {
				state.last = text;
				emit({ type: "presence", chatId: chatId, presence: now });
			}
		}, 400);
		watched = state;
		return first;
	}

	// WhatsApp's own notifications ----------------------------------------------------------------------

	// While the add-on reads new messages out, WhatsApp's banner and sound for them are held back.
	// Calls and reactions still notify as usual. If the add-on stops checking in, they come back.
	const HEARTBEAT_LIMIT_MS = 60000;
	let quiet = null;
	let lastHeartbeat = 0;

	function quietNotifications(on) {
		if (on && !quiet) {
			const proto = req("WAWebMsgNotification").WAMsgNotification.prototype;
			quiet = {
				proto: proto,
				shouldShowBanner: proto.shouldShowBanner,
				shouldPlaySound: proto.shouldPlaySound,
			};
			proto.shouldShowBanner = function () {
				return lastHeartbeat && Date.now() - lastHeartbeat < HEARTBEAT_LIMIT_MS
					? false
					: quiet.shouldShowBanner.apply(this, arguments);
			};
			proto.shouldPlaySound = function () {
				return lastHeartbeat && Date.now() - lastHeartbeat < HEARTBEAT_LIMIT_MS
					? false
					: quiet.shouldPlaySound.apply(this, arguments);
			};
			lastHeartbeat = Date.now();
		} else if (!on && quiet) {
			quiet.proto.shouldShowBanner = quiet.shouldShowBanner;
			quiet.proto.shouldPlaySound = quiet.shouldPlaySound;
			quiet = null;
		}
		return !!quiet;
	}

	function heartbeat() {
		lastHeartbeat = Date.now();
		return !!quiet;
	}

	// Events ---------------------------------------------------------------------------------------------

	const handlers = [];
	let callTimer = null;
	let chatsTimer = null;

	function chatsChanged() {
		if (chatsTimer) {
			return;
		}
		chatsTimer = setTimeout(() => {
			chatsTimer = null;
			emit({ type: "chatsChanged" });
		}, 700);
	}

	function on(collection, event, handler) {
		collection.on(event, handler);
		handlers.push([collection, event, handler]);
	}

	function hook() {
		const C = collections();
		on(C.Msg, "add", (m) => {
			if (!m.isNewMsg || HIDDEN_TYPES.has(m.type) || m.isNotification) {
				return;
			}
			const chat = m.id.remote && C.Chat.get(m.id.remote);
			if (!chat || !isListedChat(chat)) {
				return;
			}
			emit({
				type: "message",
				message: messageInfo(m),
				chat: { id: chat.id._serialized, title: chatTitle(chat), isGroup: isGroupChat(chat), muted: !!(chat.mute && chat.mute.isMuted) },
			});
		});
		// A message edited after it was sent, by its sender: on this computer, the phone, or someone else's.
		const edited = (m) => {
			if (m.latestEditMsgKey && m.id && m.id.remote) {
				emit({ type: "edited", chatId: m.id.remote._serialized, message: messageInfo(m) });
			}
		};
		on(C.Msg, "change:latestEditMsgKey", edited);
		on(C.Msg, "change:body", edited);
		on(C.Msg, "change:ack", (m) => {
			if (m.id.fromMe) {
				emit({ type: "ack", messageId: msgId(m), chatId: m.id.remote._serialized, ack: m.ack });
			}
		});
		const reactionsChanged = (model) => {
			try {
				const messageId = String(model.id);
				emit({ type: "reactions", messageId: messageId, reactions: reactionSummary(model) });
			} catch (e) {
				// A reaction WhatsApp keeps in another shape is left out.
			}
		};
		if (C.Reactions) {
			on(C.Reactions, "add", reactionsChanged);
			on(C.Reactions, "change", reactionsChanged);
		}
		hookMicrophone();
		// Calls: report every change of the call's state, from ringing to ended.
		let lastCall = "null";
		callTimer = setInterval(() => {
			let now;
			try {
				now = callState();
			} catch (e) {
				return;
			}
			const text = JSON.stringify(now);
			if (text !== lastCall) {
				lastCall = text;
				emit({ type: "call", call: now });
			}
		}, 300);
		const connectionChanged = () => emit({ type: "connection", state: connectionState() });
		on(req("WAWebStreamModel").Stream, "change:info", connectionChanged);
		on(req("WAWebStreamModel").Stream, "change:mode", connectionChanged);
		on(C.Chat, "change:unreadCount", chatsChanged);
		on(C.Chat, "change:t", chatsChanged);
		on(C.Chat, "add", chatsChanged);
		on(C.Chat, "remove", chatsChanged);
	}

	function unhook() {
		for (const [collection, event, handler] of handlers.splice(0)) {
			try {
				collection.off(event, handler);
			} catch (e) {
				// Already gone.
			}
		}
		stopAudio();
		quietNotifications(false);
		unhookMicrophone();
		if (callTimer) {
			clearInterval(callTimer);
			callTimer = null;
		}
		if (watched) {
			clearInterval(watched.timer);
			watched = null;
		}
	}

	let hooked = false;

	window.__waAccess = {
		version: VERSION,
		ready: ready,
		isHooked: () => hooked,
		install: () => {
			if (!hooked && ready()) {
				hook();
				hooked = true;
			}
			return hooked;
		},
		unhook: () => {
			unhook();
			hooked = false;
		},
		authState: authState,
		requestLinkCode: requestLinkCode,
		logout: logout,
		chats: chats,
		messages: messages,
		loadEarlier: loadEarlier,
		sendText: sendText,
		markSeen: markSeen,
		microphones: microphones,
		startRecording: startRecording,
		stopRecording: stopRecording,
		cancelRecording: cancelRecording,
		pauseRecording: pauseRecording,
		participants: participants,
		quietNotifications: quietNotifications,
		heartbeat: heartbeat,
		presence: presence,
		callState: callState,
		statuses: statuses,
		statusSeen: statusSeen,
		likeStatus: likeStatus,
		replyStatus: replyStatus,
		recentCalls: recentCalls,
		setCallAudio: setCallAudio,
		answerCall: answerCall,
		declineCall: declineCall,
		endCall: endCall,
		muteCall: muteCall,
		startCall: startCall,
		contactInfo: contactInfo,
		pollInfo: pollInfo,
		vote: vote,
		openInWhatsApp: openInWhatsApp,
		watchPresence: watchPresence,
		isRecording: () => !!recording,
		sendRecording: sendRecording,
		suggestedFileName: suggestedFileName,
		downloadStart: downloadStart,
		downloadChunk: downloadChunk,
		downloadEnd: downloadEnd,
		uploadStart: uploadStart,
		uploadChunk: uploadChunk,
		uploadCancel: uploadCancel,
		sendFile: sendFile,
		playRecording: playRecording,
		audioDevices: audioDevices,
		emojiSuggestions: emojiSuggestions,
		playMessage: playMessage,
		messageActions: messageActions,
		setTyping: setTyping,
		forward: forward,
		messageReceipts: messageReceipts,
		chatWithNumber: chatWithNumber,
		searchMessages: searchMessages,
		allMessages: allMessages,
		reactions: reactions,
		react: react,
		star: star,
		editText: editText,
		deleteMessage: deleteMessage,
		chatAction: chatAction,
		messagesActions: messagesActions,
		deleteMessages: deleteMessages,
		starMessages: starMessages,
		chatsAction: chatsAction,
		starredMessages: starredMessages,
		channels: channels,
		searchChannels: searchChannels,
		followChannel: followChannel,
		communities: communities,
		joinCommunityGroup: joinCommunityGroup,
		chatAbilities: chatAbilities,
		contactChoices: contactChoices,
		createGroup: createGroup,
		changeParticipants: changeParticipants,
		setGroupInfo: setGroupInfo,
		setGroupSetting: setGroupSetting,
		inviteLink: inviteLink,
		exitGroup: exitGroup,
		deleteChat: deleteChat,
		clearChat: clearChat,
		setBlocked: setBlocked,
		reportChat: reportChat,
		setDisappearing: setDisappearing,
		setFavorite: setFavorite,
		sendPoll: sendPoll,
		pinMessage: pinMessage,
		pinnedMessages: pinnedMessages,
		replyPrivately: replyPrivately,
		reactionDetails: reactionDetails,
		sendContacts: sendContacts,
		stickers: stickers,
		sendSticker: sendSticker,
		searchAll: searchAll,
		chatMedia: chatMedia,
		unreadMentions: unreadMentions,
		eventInfo: eventInfo,
		respondToEvent: respondToEvent,
		createEvent: createEvent,
		postTextStatus: postTextStatus,
		myStatuses: myStatuses,
		deleteMyStatus: deleteMyStatus,
		profile: profile,
		setProfile: setProfile,
		setProfilePhoto: setProfilePhoto,
		privacy: privacy,
		setPrivacy: setPrivacy,
		blockedContacts: blockedContacts,
		unblock: unblock,
		startGroupCall: startGroupCall,
		ongoingGroupCall: ongoingGroupCall,
		joinGroupCall: joinGroupCall,
		connectionState: connectionState,
		setOnline: setOnline,
		raiseHand: raiseHand,
		callReaction: callReaction,
		askToMute: askToMute,
		speakers: speakers,
		stopAudio: stopAudio,
		setPlaybackRate: setPlaybackRate,
		setPlaybackVolume: setPlaybackVolume,
		setCallVolume: setCallVolume,
	};
})();
